"""Risk computation engine for position sizing, ladders, and risk assessment."""
import math
from typing import Optional

from app.config.loader import load_strategy_settings, get_product_config
from app.contracts.risk import (
    LadderLevel,
    LadderPlan,
    PositionSizing,
    RiskProfile,
    TradeRiskAssessment,
)
from app.core.exceptions import RiskError
from app.core.logging import get_logger
from app.services.cache import CacheManager

logger = get_logger(__name__)


class RiskEngine:
    """Computes risk profiles, position sizing, and ladder plans."""

    def __init__(self) -> None:
        self._cache = CacheManager()
        self._risk_settings = load_strategy_settings().get("risk", {})

    # --- Tick Helpers ---

    @staticmethod
    def price_to_ticks(price_diff: float, tick_size: float) -> float:
        """Convert a price difference to number of ticks."""
        if tick_size <= 0:
            raise RiskError("tick_size must be positive")
        return round(price_diff / tick_size, 4)

    @staticmethod
    def ticks_to_price(ticks: float, tick_size: float) -> float:
        """Convert tick count to price units."""
        return round(ticks * tick_size, 8)

    @staticmethod
    def ticks_to_dollars(ticks: float, tick_value: float) -> float:
        """Convert ticks to dollar amount."""
        return round(ticks * tick_value, 2)

    @staticmethod
    def spread_bp_to_ticks(spread_bp: float, spread_tick_size_bp: float) -> float:
        """Convert spread basis points to ticks."""
        if spread_tick_size_bp <= 0:
            raise RiskError("spread_tick_size_bp must be positive")
        return round(spread_bp / spread_tick_size_bp, 4)

    # --- Risk Profile ---

    def compute_risk_profile(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_price: float,
        target_price: float,
        product_key: str,
        is_spread: bool = False,
    ) -> RiskProfile:
        """Compute complete risk profile for a planned trade."""
        product = get_product_config(product_key)

        if is_spread:
            tick_size = product["spread_tick_size_bp"]
            tick_value = product["spread_tick_value"]
        else:
            tick_size = product["outright_tick_size"]
            tick_value = product["outright_tick_value"]

        if direction == "long":
            risk_price = entry_price - stop_price
            reward_price = target_price - entry_price
        else:
            risk_price = stop_price - entry_price
            reward_price = entry_price - target_price

        risk_ticks = self.price_to_ticks(abs(risk_price), tick_size)
        reward_ticks = self.price_to_ticks(abs(reward_price), tick_size)

        rr_ratio = reward_ticks / risk_ticks if risk_ticks > 0 else 0.0

        # Position sizing
        sizing = self._compute_sizing(risk_ticks, tick_value, symbol)

        # Ladder plans
        entry_ladder = self._build_ladder(
            entry_price, tick_size, tick_value, direction, "entry", sizing.volatility_adjusted_lots
        )
        stop_ladder = self._build_ladder(
            stop_price, tick_size, tick_value, direction, "stop", sizing.volatility_adjusted_lots
        )
        target_ladder = self._build_ladder(
            target_price, tick_size, tick_value, direction, "target", sizing.volatility_adjusted_lots
        )

        return RiskProfile(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            tick_size=tick_size,
            tick_value=tick_value,
            risk_ticks=risk_ticks,
            reward_ticks=reward_ticks,
            risk_reward_ratio=round(rr_ratio, 2),
            sizing=sizing,
            entry_ladder=entry_ladder,
            stop_ladder=stop_ladder,
            target_ladder=target_ladder,
        )

    def _compute_sizing(
        self,
        risk_ticks: float,
        tick_value: float,
        symbol: str,
    ) -> PositionSizing:
        """Compute position sizing based on risk constraints."""
        account = self._cache.get_account()
        max_risk = account.get("max_risk_per_trade_usd", 50000.0)
        max_lots = account.get("max_position_lots", 100)
        slippage_ticks = account.get("default_slippage_ticks", 1)
        commission = account.get("default_commission_per_lot", 2.50)

        risk_per_lot = self.ticks_to_dollars(risk_ticks, tick_value)
        if risk_per_lot <= 0:
            base_lots = 0
        else:
            base_lots = min(int(max_risk / risk_per_lot), max_lots)

        # Volatility-adjusted sizing
        vol_lots = base_lots
        if self._risk_settings.get("volatility_scaling_enabled", False):
            indicators = self._cache.get_indicators(symbol, "1H")
            if indicators and indicators.atr and indicators.atr.values:
                atr_values = indicators.atr.values
                if len(atr_values) >= 2:
                    current_atr = atr_values[-1]
                    avg_atr = sum(atr_values[-20:]) / min(len(atr_values), 20)
                    if current_atr > 0 and avg_atr > 0:
                        vol_factor = avg_atr / current_atr
                        vol_lots = max(1, min(int(base_lots * vol_factor), max_lots))

        slippage_usd = self.ticks_to_dollars(slippage_ticks, tick_value) * vol_lots
        commission_usd = commission * vol_lots
        total_risk = risk_per_lot * vol_lots
        net_risk = total_risk + slippage_usd + commission_usd

        return PositionSizing(
            base_lots=base_lots,
            volatility_adjusted_lots=vol_lots,
            max_allowed_lots=max_lots,
            risk_per_lot=risk_per_lot,
            total_risk_usd=total_risk,
            slippage_estimate_usd=slippage_usd,
            commission_estimate_usd=commission_usd,
            net_risk_usd=net_risk,
        )

    def _build_ladder(
        self,
        base_price: float,
        tick_size: float,
        tick_value: float,
        direction: str,
        ladder_type: str,
        total_lots: int,
    ) -> LadderPlan:
        """Build a multi-level ladder plan."""
        max_levels = self._risk_settings.get("max_ladder_levels", 5)
        scale_factor = self._risk_settings.get("ladder_scale_factor", 1.5)

        levels: list[LadderLevel] = []
        remaining_lots = total_lots

        for lvl in range(1, max_levels + 1):
            if remaining_lots <= 0:
                break

            if ladder_type == "entry":
                if direction == "long":
                    price = base_price - (lvl - 1) * tick_size
                else:
                    price = base_price + (lvl - 1) * tick_size
            elif ladder_type == "target":
                if direction == "long":
                    price = base_price + (lvl - 1) * tick_size * 2
                else:
                    price = base_price - (lvl - 1) * tick_size * 2
            else:  # stop
                price = base_price

            if lvl == max_levels:
                lots_at_level = remaining_lots
            else:
                lots_at_level = max(1, int(remaining_lots / (max_levels - lvl + 1)))

            ticks_from_entry = self.price_to_ticks(abs(price - base_price), tick_size)
            pnl_per_lot = self.ticks_to_dollars(ticks_from_entry, tick_value)

            levels.append(
                LadderLevel(
                    level_num=lvl,
                    price=round(price, 6),
                    ticks_from_entry=ticks_from_entry,
                    pnl_per_lot=pnl_per_lot,
                    lots=lots_at_level,
                )
            )
            remaining_lots -= lots_at_level

        # Compute cumulative
        cum_pnl = 0.0
        total = 0
        weighted_sum = 0.0
        for level in levels:
            cum_pnl += level.pnl_per_lot * level.lots
            level.cumulative_pnl = round(cum_pnl, 2)
            weighted_sum += level.price * level.lots
            total += level.lots

        wavg = weighted_sum / total if total > 0 else base_price

        return LadderPlan(
            levels=levels,
            total_lots=total,
            weighted_avg_price=round(wavg, 6),
        )

    def assess_trade(
        self,
        risk_profile: RiskProfile,
        symbol: str,
        timeframe: str = "1H",
    ) -> TradeRiskAssessment:
        """Full trade risk assessment with market context."""
        regime = self._cache.get_regime()
        indicators = self._cache.get_indicators(symbol, timeframe)
        warnings: list[str] = []

        current_atr: float | None = None
        atr_mult_risk: float | None = None
        atr_mult_reward: float | None = None
        vol_pct: float | None = None

        if indicators and indicators.atr and indicators.atr.values:
            atr_vals = indicators.atr.values
            current_atr = atr_vals[-1]
            if current_atr > 0:
                risk_price = risk_profile.risk_ticks * risk_profile.tick_size
                reward_price = risk_profile.reward_ticks * risk_profile.tick_size
                atr_mult_risk = round(risk_price / current_atr, 2)
                atr_mult_reward = round(reward_price / current_atr, 2)

                if atr_mult_risk < 0.5:
                    warnings.append("Stop is very tight relative to ATR — high probability of being stopped out")
                if atr_mult_risk > 3.0:
                    warnings.append("Stop is very wide relative to ATR — consider tighter risk")

            if len(atr_vals) >= 20:
                sorted_atr = sorted(atr_vals[-100:] if len(atr_vals) >= 100 else atr_vals)
                rank = sum(1 for v in sorted_atr if v <= current_atr)
                vol_pct = round(rank / len(sorted_atr) * 100, 1)
                if vol_pct > 90:
                    warnings.append("Volatility is at extreme levels — reduce size or widen stops")

        if risk_profile.risk_reward_ratio < 1.0:
            warnings.append("Risk/reward ratio is below 1:1")

        if risk_profile.sizing and risk_profile.sizing.net_risk_usd > self._risk_settings.get("max_risk_per_trade_usd", 50000):
            warnings.append("Net risk exceeds maximum per-trade risk limit")

        return TradeRiskAssessment(
            risk_profile=risk_profile,
            current_atr=current_atr,
            atr_multiple_risk=atr_mult_risk,
            atr_multiple_reward=atr_mult_reward,
            regime=regime.regime.value,
            macro_bias=regime.macro_bias.value,
            volatility_percentile=vol_pct,
            warnings=warnings,
        )
