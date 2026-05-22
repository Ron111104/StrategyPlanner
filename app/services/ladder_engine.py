"""Adaptive Strategy Ladder Engine.

Dynamically generates institutional-grade entry ladders, stops, targets,
and position sizing based on OHLCV, ATR, DCW, volatility, regime, strategy,
timeframe, and market structure. This is the core engine of the platform.

Trader does NOT manually enter ladder prices — all levels are computed
automatically from market data and indicator context.
"""
import math
from typing import Optional

from app.config.loader import get_product_config, load_strategy_settings
from app.contracts.indicators import IndicatorSet
from app.contracts.ladder import AdaptiveLadder, AdaptiveLadderLevel, LadderRequest
from app.contracts.market_data import OHLCVSeries
from app.contracts.regime import RegimeState, RegimeType
from app.core.exceptions import InsufficientDataError, RiskError
from app.core.logging import get_logger
from app.services.cache import CacheManager
from app.services.indicator_engine import IndicatorEngine

logger = get_logger(__name__)

# Spacing multipliers per regime
REGIME_SPACING: dict[str, dict[str, float]] = {
    "trend": {"atr_mult": 0.5, "dcw_mult": 0.0, "source": "ATR"},
    "range": {"atr_mult": 0.0, "dcw_mult": 0.25, "source": "DCW"},
    "volatility": {"atr_mult": 1.2, "dcw_mult": 0.0, "source": "ATR"},
    "event": {"atr_mult": 0.0, "dcw_mult": 0.0, "source": "NONE"},
}

# Lot distribution profiles: weights per level (normalized)
LOT_PROFILES: dict[str, list[float]] = {
    "pyramid": [1.0, 1.5, 2.5, 3.5, 5.0],
    "equal": [1.0, 1.0, 1.0, 1.0, 1.0],
    "front_loaded": [3.0, 2.5, 2.0, 1.5, 1.0],
    "back_loaded": [1.0, 1.5, 2.0, 2.5, 3.0],
}

# Strategy → direction logic and lot profile
STRATEGY_DEFAULTS: dict[str, dict] = {
    "trend_fed_repricing": {"lot_profile": "pyramid", "target_atr_mult": [2.0, 4.0], "stop_atr_mult": 1.5},
    "mean_reversion_range": {"lot_profile": "front_loaded", "target_atr_mult": [1.5, 2.5], "stop_atr_mult": 1.0},
    "event_momentum": {"lot_profile": "equal", "target_atr_mult": [2.5, 5.0], "stop_atr_mult": 2.0},
    "event_fade": {"lot_profile": "equal", "target_atr_mult": [1.0, 2.0], "stop_atr_mult": 1.5},
    "volatility_fade": {"lot_profile": "front_loaded", "target_atr_mult": [1.5, 3.0], "stop_atr_mult": 1.2},
    "curve_steepener": {"lot_profile": "pyramid", "target_atr_mult": [2.0, 4.0], "stop_atr_mult": 1.5},
    "curve_flattener": {"lot_profile": "pyramid", "target_atr_mult": [2.0, 4.0], "stop_atr_mult": 1.5},
}

# Timeframe multipliers for spacing adjustment
TIMEFRAME_MULT: dict[str, float] = {
    "1M": 0.3,
    "5M": 0.5,
    "15M": 0.7,
    "1H": 1.0,
    "4H": 1.5,
    "1D": 2.5,
}


class LadderEngine:
    """Generates adaptive strategy ladders from market data and indicators."""

    def __init__(self) -> None:
        self._cache = CacheManager()
        self._indicator_engine = IndicatorEngine()
        self._risk_settings = load_strategy_settings().get("risk", {})
        self._ladder_settings = load_strategy_settings().get("ladder", {})

    def generate(self, request: LadderRequest) -> AdaptiveLadder:
        """Generate a complete adaptive strategy ladder."""
        product = get_product_config(request.product_key)
        is_spread = "-" in request.symbol
        instrument_type = "spread" if is_spread else "outright"

        # Resolve tick parameters
        if is_spread:
            tick_size = product["spread_tick_size_bp"]
            tick_value = product["spread_tick_value"]
        else:
            tick_size = product["outright_tick_size"]
            tick_value = product["outright_tick_value"]

        # Get market data
        series = self._cache.get_ohlcv(request.symbol, request.timeframe)
        if not series or series.is_empty:
            raise InsufficientDataError(f"No OHLCV data for {request.symbol}:{request.timeframe}")

        # Get or compute indicators
        indicators = self._cache.get_indicators(request.symbol, request.timeframe)
        if not indicators:
            indicators = self._indicator_engine.compute_all(series)

        # Get regime
        regime_state = self._cache.get_regime()
        regime_str = regime_state.regime.value
        macro_bias = regime_state.macro_bias.value

        # Get account limits
        account = self._cache.get_account()
        max_lots = request.max_lots or account.get("max_position_lots", 100)
        max_risk = request.max_risk_usd or account.get("max_risk_per_trade_usd", 50000.0)

        # Determine direction
        direction = request.direction or self._infer_direction(
            request.strategy, series, indicators, regime_state, macro_bias
        )

        # Extract current price as entry reference
        entry_ref = series.latest.close

        # Extract ATR and DCW
        current_atr = self._get_latest_value(indicators.atr)
        current_dcw = self._get_latest_value(indicators.dcw)

        if current_atr is None and current_dcw is None:
            raise InsufficientDataError("Need ATR or DCW to generate ladder")

        # Compute spacing
        spacing, spacing_method = self._compute_spacing(
            regime_str, request.timeframe, current_atr, current_dcw, tick_size, is_spread
        )

        # Event regime = single entry only
        if regime_str == "event":
            max_levels = 1
        else:
            max_levels = min(request.max_levels, self._ladder_settings.get("max_levels", 5))

        # Compute volatility percentile
        vol_pct = self._compute_vol_percentile(indicators)

        # Get strategy defaults
        strat_defaults = STRATEGY_DEFAULTS.get(request.strategy, STRATEGY_DEFAULTS["trend_fed_repricing"])

        # Build ladder levels
        levels = self._build_levels(
            entry_ref=entry_ref,
            direction=direction,
            spacing=spacing,
            max_levels=max_levels,
            max_lots=max_lots,
            max_risk=max_risk,
            tick_size=tick_size,
            tick_value=tick_value,
            lot_profile_name=strat_defaults["lot_profile"],
            is_spread=is_spread,
        )

        # Compute aggregate stats
        total_lots = sum(lv.lots for lv in levels)
        avg_entry = self._weighted_avg(levels)

        # Compute stop and targets
        stop_mult = strat_defaults["stop_atr_mult"]
        target_mults = strat_defaults["target_atr_mult"]
        atr_for_calc = current_atr if current_atr and current_atr > 0 else (current_dcw or spacing)

        stop = self._compute_stop(avg_entry, direction, atr_for_calc, stop_mult, is_spread)
        target_1 = self._compute_target(avg_entry, direction, atr_for_calc, target_mults[0], is_spread)
        target_2 = self._compute_target(avg_entry, direction, atr_for_calc, target_mults[1], is_spread) if len(target_mults) > 1 else None

        # Risk/reward
        stop_dist = abs(avg_entry - stop)
        target_dist = abs(target_1 - avg_entry)
        stop_ticks = stop_dist / tick_size if tick_size > 0 else 0
        risk_reward = target_dist / stop_dist if stop_dist > 0 else 0.0
        total_risk = stop_ticks * tick_value * total_lots
        total_reward = (target_dist / tick_size * tick_value * total_lots) if tick_size > 0 else 0.0

        # MTF alignment score
        mtf_align = self._compute_mtf_alignment(request.symbol, request.timeframe, direction, indicators)

        # Confidence based on strategy signal + volatility + MTF
        base_conf = 0.6
        if vol_pct is not None:
            if 20 < vol_pct < 80:
                base_conf += 0.1
        if mtf_align and mtf_align > 0.5:
            base_conf += 0.1
        if regime_str in ("trend", "range"):
            base_conf += 0.05
        confidence = min(1.0, base_conf)

        # Build bp values for spreads
        entry_bp = entry_ref if is_spread else None
        avg_bp = avg_entry if is_spread else None
        stop_bp = stop if is_spread else None
        t1_bp = target_1 if is_spread else None
        t2_bp = target_2 if is_spread else None

        return AdaptiveLadder(
            strategy=request.strategy,
            symbol=request.symbol,
            product_key=request.product_key,
            timeframe=request.timeframe,
            direction=direction,
            instrument_type=instrument_type,
            regime=regime_str,
            macro_bias=macro_bias,
            entry_reference=round(entry_ref, 6),
            entry_reference_bp=entry_bp,
            levels=levels,
            total_lots=total_lots,
            avg_entry=round(avg_entry, 6),
            avg_entry_bp=avg_bp,
            stop=round(stop, 6),
            stop_bp=stop_bp,
            stop_distance_ticks=round(stop_ticks, 2),
            target_1=round(target_1, 6),
            target_1_bp=t1_bp,
            target_2=round(target_2, 6) if target_2 is not None else None,
            target_2_bp=t2_bp,
            risk_reward=round(risk_reward, 2),
            total_risk_usd=round(total_risk, 2),
            total_reward_usd=round(total_reward, 2),
            spacing_method=spacing_method,
            spacing_value=round(spacing, 6),
            confidence=round(confidence, 3),
            atr_at_generation=round(current_atr, 6) if current_atr else None,
            dcw_at_generation=round(current_dcw, 6) if current_dcw else None,
            vol_percentile=vol_pct,
            mtf_alignment=mtf_align,
        )

    # ---- Internal Helpers ----

    def _get_latest_value(self, result) -> Optional[float]:
        if result and result.values:
            return result.values[-1]
        return None

    def _compute_spacing(
        self, regime: str, timeframe: str,
        atr: Optional[float], dcw: Optional[float],
        tick_size: float, is_spread: bool,
    ) -> tuple[float, str]:
        """Compute ladder level spacing from regime, ATR, DCW, timeframe."""
        cfg = REGIME_SPACING.get(regime, REGIME_SPACING["trend"])
        tf_mult = TIMEFRAME_MULT.get(timeframe, 1.0)

        if cfg["source"] == "ATR" and atr and atr > 0:
            raw = atr * cfg["atr_mult"]
            method = f"ATR×{cfg['atr_mult']}"
        elif cfg["source"] == "DCW" and dcw and dcw > 0:
            raw = dcw * cfg["dcw_mult"]
            method = f"DCW×{cfg['dcw_mult']}"
        elif atr and atr > 0:
            raw = atr * 0.5
            method = "ATR×0.5 (fallback)"
        elif dcw and dcw > 0:
            raw = dcw * 0.25
            method = "DCW×0.25 (fallback)"
        else:
            raw = tick_size * 3
            method = f"tick×3 (no ATR/DCW)"

        # Apply timeframe multiplier
        spacing = raw * tf_mult

        # Snap to tick grid
        if tick_size > 0:
            spacing = max(tick_size, round(spacing / tick_size) * tick_size)

        return spacing, method

    def _build_levels(
        self, entry_ref: float, direction: str, spacing: float,
        max_levels: int, max_lots: int, max_risk: float,
        tick_size: float, tick_value: float,
        lot_profile_name: str, is_spread: bool,
    ) -> list[AdaptiveLadderLevel]:
        """Build ladder levels with lot distribution."""
        profile = LOT_PROFILES.get(lot_profile_name, LOT_PROFILES["pyramid"])
        # Truncate or extend profile to max_levels
        if len(profile) < max_levels:
            profile = profile + [profile[-1]] * (max_levels - len(profile))
        profile = profile[:max_levels]
        total_weight = sum(profile)

        # Determine direction sign
        # Long entries go DOWN from reference, short entries go UP
        # Steepener (spread long) entries go DOWN, flattener (spread short) go UP
        if direction in ("long", "steepener"):
            sign = -1.0
        else:
            sign = 1.0

        levels = []
        cum_lots = 0
        for i in range(max_levels):
            offset = spacing * i * sign
            price = entry_ref + offset

            # Snap to tick grid
            if tick_size > 0:
                price = round(round(price / tick_size) * tick_size, 6)

            # Lots at this level
            raw_lots = max(1, int((profile[i] / total_weight) * max_lots))

            # Check risk constraint
            distance_from_ref = abs(price - entry_ref)
            dist_ticks = distance_from_ref / tick_size if tick_size > 0 else 0.0
            level_risk = dist_ticks * tick_value * raw_lots if i > 0 else 0.0

            cum_lots += raw_lots

            levels.append(AdaptiveLadderLevel(
                level=i + 1,
                entry_price=round(price, 6),
                entry_bp=round(price, 2) if is_spread else None,
                lots=raw_lots,
                cumulative_lots=cum_lots,
                distance_from_ref=round(distance_from_ref, 6),
                distance_ticks=round(dist_ticks, 2),
                risk_usd=round(level_risk, 2),
            ))

        return levels

    def _weighted_avg(self, levels: list[AdaptiveLadderLevel]) -> float:
        total_lots = sum(lv.lots for lv in levels)
        if total_lots == 0:
            return levels[0].entry_price if levels else 0.0
        return sum(lv.entry_price * lv.lots for lv in levels) / total_lots

    def _compute_stop(
        self, avg_entry: float, direction: str,
        atr: float, mult: float, is_spread: bool,
    ) -> float:
        dist = atr * mult
        if direction in ("long", "steepener"):
            return avg_entry - dist
        return avg_entry + dist

    def _compute_target(
        self, avg_entry: float, direction: str,
        atr: float, mult: float, is_spread: bool,
    ) -> float:
        dist = atr * mult
        if direction in ("long", "steepener"):
            return avg_entry + dist
        return avg_entry - dist

    def _compute_vol_percentile(self, indicators: IndicatorSet) -> Optional[float]:
        if indicators.atr and indicators.atr.values and len(indicators.atr.values) >= 20:
            vals = indicators.atr.values
            current = vals[-1]
            lookback = vals[-100:] if len(vals) >= 100 else vals
            rank = sum(1 for v in lookback if v <= current)
            return round(rank / len(lookback) * 100, 1)
        return None

    def _infer_direction(
        self, strategy: str, series: OHLCVSeries,
        indicators: IndicatorSet, regime: RegimeState, macro_bias: str,
    ) -> str:
        """Infer trade direction from strategy, indicators, and macro bias."""
        is_spread = "-" in series.symbol

        # Curve strategies have fixed direction
        if strategy == "curve_steepener":
            return "steepener"
        if strategy == "curve_flattener":
            return "flattener"

        # For event fade, direction opposes the recent move
        if strategy == "event_fade":
            if series.bars and len(series.bars) >= 2:
                move = series.bars[-1].close - series.bars[-2].close
                return "short" if move > 0 else "long"

        # For mean reversion, direction opposes distance from mean
        if strategy == "mean_reversion_range":
            if indicators.bollinger and indicators.bollinger.values:
                mid = indicators.bollinger.values[-1]
                last = series.latest.close
                return "long" if last < mid else "short"

        # EMA trend for trend strategies
        ema_short = indicators.ema.get(9)
        ema_long = indicators.ema.get(21)
        if ema_short and ema_long and ema_short.values and ema_long.values:
            if ema_short.values[-1] > ema_long.values[-1]:
                return "long"
            return "short"

        # Macro bias fallback
        if macro_bias == "dovish":
            return "long"
        if macro_bias == "hawkish":
            return "short"

        return "long"

    def _compute_mtf_alignment(
        self, symbol: str, current_tf: str,
        direction: str, indicators: IndicatorSet,
    ) -> Optional[float]:
        """Score multi-timeframe alignment (0-1)."""
        tf_order = ["1M", "5M", "15M", "1H", "4H", "1D"]
        current_idx = tf_order.index(current_tf) if current_tf in tf_order else -1
        if current_idx < 0:
            return None

        aligned = 0
        checked = 0

        # Check higher timeframes
        for tf in tf_order[current_idx + 1:]:
            htf_ind = self._cache.get_indicators(symbol, tf)
            if htf_ind:
                ema_s = htf_ind.ema.get(9)
                ema_l = htf_ind.ema.get(21)
                if ema_s and ema_l and ema_s.values and ema_l.values:
                    checked += 1
                    htf_bullish = ema_s.values[-1] > ema_l.values[-1]
                    if (direction in ("long", "steepener") and htf_bullish) or \
                       (direction in ("short", "flattener") and not htf_bullish):
                        aligned += 1

        if checked == 0:
            return None
        return round(aligned / checked, 2)
