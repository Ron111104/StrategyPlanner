"""
Strategy definitions for CME Fed Funds Futures (ZQ) Strategy Planning Platform.

Seven complete strategies with full entry/stop/target evaluation logic:
1. TrendFedRepricing   – Trend-following EMA crossover with ATR confirmation
2. MeanReversionRange  – Bollinger band mean-reversion in range regimes
3. EventMomentum       – Donchian breakout on macro events
4. EventFade           – Fade extreme event moves (>2σ)
5. VolatilityFade      – Fade vol spikes at Bollinger extremes
6. CurveSteepener      – Buy front / sell back on narrow spreads
7. CurveFlattener      – Sell front / buy back on wide spreads
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import structlog

from app.contracts.macro_inputs import MacroBias, MarketRegime, RegimeState
from app.contracts.market_data import OHLCVBar

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Signal parameters returned by each strategy's evaluate()
# ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class SignalParams:
    """Parameters returned when a strategy fires a signal."""
    direction: str            # "long" or "short"
    entry_price: float
    stop_price: float
    target_price: float
    confidence: float         # 0.0 – 1.0
    reason: str
    risk_multiplier: float    # strategy-specific multiplier for position sizing


# ──────────────────────────────────────────────────────────────────────
# Base strategy definition
# ──────────────────────────────────────────────────────────────────────

@dataclass
class StrategyDefinition:
    """Base class for all strategy definitions."""
    name: str
    description: str
    applicable_regimes: list[MarketRegime]
    applicable_products: list[str]   # "outright", "spread"
    priority: int                     # lower = higher priority
    risk_multiplier: float
    volatility_suitability: list[str] # "low", "medium", "high"
    enabled: bool = True

    def is_applicable(self, regime: RegimeState, product_type: str) -> bool:
        """Check if this strategy applies to the given regime and product type."""
        if not self.enabled:
            return False
        if regime.regime not in self.applicable_regimes:
            return False
        if product_type not in self.applicable_products:
            return False
        return True

    def evaluate(
        self,
        bars: list[OHLCVBar],
        indicators: dict[str, Any],
        regime: RegimeState,
    ) -> SignalParams | None:
        """Evaluate this strategy and return signal params, or None."""
        raise NotImplementedError


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _last_valid(series: list[float], offset: int = 0) -> float | None:
    """Return the (len-1-offset)th non-NaN value, or None."""
    idx = len(series) - 1 - offset
    if idx < 0:
        return None
    v = series[idx]
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return v


def _last_n_valid(series: list[float], n: int) -> list[float]:
    """Return last *n* non-NaN values from series."""
    result: list[float] = []
    for v in reversed(series):
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            result.append(v)
            if len(result) == n:
                break
    result.reverse()
    return result


# ══════════════════════════════════════════════════════════════════════
# 1. Trend Fed Repricing
# ══════════════════════════════════════════════════════════════════════

@dataclass
class TrendFedRepricing(StrategyDefinition):
    """Trend-following: EMA21 crossover with ATR confirmation.

    Entry : Price crosses above / below EMA21 with elevated ATR.
    Stop  : 2× ATR from entry.
    Target: Next Donchian level or 3× ATR (whichever is closer to entry).
    """

    name: str = "TrendFedRepricing"
    description: str = (
        "Trend-following strategy using EMA21 crossover with ATR "
        "confirmation, targeting Donchian channel levels."
    )
    applicable_regimes: list[MarketRegime] = field(
        default_factory=lambda: [MarketRegime.TREND]
    )
    applicable_products: list[str] = field(
        default_factory=lambda: ["outright", "spread"]
    )
    priority: int = 1
    risk_multiplier: float = 1.0
    volatility_suitability: list[str] = field(
        default_factory=lambda: ["medium", "high"]
    )

    def evaluate(
        self,
        bars: list[OHLCVBar],
        indicators: dict[str, Any],
        regime: RegimeState,
    ) -> SignalParams | None:
        if regime.regime in (MarketRegime.EVENT, MarketRegime.RANGE):
            return None

        ema = indicators.get("ema", [])
        atr = indicators.get("atr", [])
        atr_sma = indicators.get("atr_sma", [])
        donchian = indicators.get("donchian", {})

        latest_ema = _last_valid(ema)
        prev_ema = _last_valid(ema, 1)
        latest_atr = _last_valid(atr)
        latest_atr_sma = _last_valid(atr_sma)
        donchian_upper = _last_valid(donchian.get("upper", []))
        donchian_lower = _last_valid(donchian.get("lower", []))

        if any(v is None for v in [latest_ema, prev_ema, latest_atr, latest_atr_sma]):
            return None

        # Need at least 2 bars for crossover check
        if len(bars) < 2:
            return None

        current_close = bars[-1].close
        prev_close = bars[-2].close

        # ATR confirmation: current ATR must be above ATR-SMA
        if latest_atr <= latest_atr_sma:  # type: ignore[operator]
            return None

        atr_ratio = latest_atr / latest_atr_sma  # type: ignore[operator]

        # ── LONG signal: price crosses above EMA21 ──
        if prev_close <= prev_ema and current_close > latest_ema:  # type: ignore[operator]
            entry = current_close
            stop = entry - 2.0 * latest_atr  # type: ignore[operator]
            # Target: Donchian upper or 3x ATR, whichever closer
            target_atr = entry + 3.0 * latest_atr  # type: ignore[operator]
            target_donchian = donchian_upper if donchian_upper is not None else target_atr
            target = min(target_atr, target_donchian) if target_donchian > entry else target_atr  # type: ignore[operator]
            if target <= entry:
                target = target_atr

            confidence = min(0.90, 0.50 + (atr_ratio - 1.0) * 0.25)
            return SignalParams(
                direction="long",
                entry_price=entry,
                stop_price=stop,
                target_price=target,
                confidence=confidence,
                reason=(
                    f"Bullish EMA21 crossover: close {current_close:.4f} > "
                    f"EMA {latest_ema:.4f}, ATR ratio {atr_ratio:.2f}"
                ),
                risk_multiplier=self.risk_multiplier,
            )

        # ── SHORT signal: price crosses below EMA21 ──
        if prev_close >= prev_ema and current_close < latest_ema:  # type: ignore[operator]
            entry = current_close
            stop = entry + 2.0 * latest_atr  # type: ignore[operator]
            target_atr = entry - 3.0 * latest_atr  # type: ignore[operator]
            target_donchian = donchian_lower if donchian_lower is not None else target_atr
            target = max(target_atr, target_donchian) if target_donchian < entry else target_atr  # type: ignore[operator]
            if target >= entry:
                target = target_atr

            confidence = min(0.90, 0.50 + (atr_ratio - 1.0) * 0.25)
            return SignalParams(
                direction="short",
                entry_price=entry,
                stop_price=stop,
                target_price=target,
                confidence=confidence,
                reason=(
                    f"Bearish EMA21 crossover: close {current_close:.4f} < "
                    f"EMA {latest_ema:.4f}, ATR ratio {atr_ratio:.2f}"
                ),
                risk_multiplier=self.risk_multiplier,
            )

        return None


# ══════════════════════════════════════════════════════════════════════
# 2. Mean Reversion Range
# ══════════════════════════════════════════════════════════════════════

@dataclass
class MeanReversionRange(StrategyDefinition):
    """Mean-reversion at Bollinger extremes during range regimes.

    Entry : Price touches Bollinger band.
    Stop  : Beyond the band by 1× ATR.
    Target: Opposite Bollinger band or middle band.
    """

    name: str = "MeanReversionRange"
    description: str = (
        "Mean-reversion strategy fading Bollinger band touches "
        "in range-bound markets."
    )
    applicable_regimes: list[MarketRegime] = field(
        default_factory=lambda: [MarketRegime.RANGE]
    )
    applicable_products: list[str] = field(
        default_factory=lambda: ["outright", "spread"]
    )
    priority: int = 2
    risk_multiplier: float = 0.8
    volatility_suitability: list[str] = field(
        default_factory=lambda: ["low", "medium"]
    )

    def evaluate(
        self,
        bars: list[OHLCVBar],
        indicators: dict[str, Any],
        regime: RegimeState,
    ) -> SignalParams | None:
        if regime.regime in (MarketRegime.TREND, MarketRegime.EVENT):
            return None

        bollinger = indicators.get("bollinger", {})
        atr = indicators.get("atr", [])
        dcw = indicators.get("dcw", [])

        bb_upper = _last_valid(bollinger.get("upper", []))
        bb_lower = _last_valid(bollinger.get("lower", []))
        bb_mid = _last_valid(bollinger.get("mid", []))
        latest_atr = _last_valid(atr)
        latest_dcw = _last_valid(dcw)

        if any(v is None for v in [bb_upper, bb_lower, bb_mid, latest_atr]):
            return None

        if not bars:
            return None

        current_close = bars[-1].close

        # Confidence based on DCW (tighter range = higher confidence)
        dcw_confidence = 0.65
        if latest_dcw is not None and latest_dcw > 0:
            # Tighter range (lower DCW) → higher confidence
            dcw_confidence = min(0.90, 0.60 + (0.01 - min(latest_dcw, 0.01)) * 30)

        # ── LONG signal: price at or below lower Bollinger ──
        if current_close <= bb_lower:  # type: ignore[operator]
            entry = current_close
            stop = bb_lower - 1.0 * latest_atr  # type: ignore[operator]
            target = bb_mid  # type: ignore[assignment]
            return SignalParams(
                direction="long",
                entry_price=entry,
                stop_price=stop,
                target_price=target,  # type: ignore[arg-type]
                confidence=dcw_confidence,
                reason=(
                    f"Mean-reversion long at lower Bollinger: close {current_close:.4f} "
                    f"<= BB lower {bb_lower:.4f}"
                ),
                risk_multiplier=self.risk_multiplier,
            )

        # ── SHORT signal: price at or above upper Bollinger ──
        if current_close >= bb_upper:  # type: ignore[operator]
            entry = current_close
            stop = bb_upper + 1.0 * latest_atr  # type: ignore[operator]
            target = bb_mid  # type: ignore[assignment]
            return SignalParams(
                direction="short",
                entry_price=entry,
                stop_price=stop,
                target_price=target,  # type: ignore[arg-type]
                confidence=dcw_confidence,
                reason=(
                    f"Mean-reversion short at upper Bollinger: close {current_close:.4f} "
                    f">= BB upper {bb_upper:.4f}"
                ),
                risk_multiplier=self.risk_multiplier,
            )

        return None


# ══════════════════════════════════════════════════════════════════════
# 3. Event Momentum
# ══════════════════════════════════════════════════════════════════════

@dataclass
class EventMomentum(StrategyDefinition):
    """Breakout beyond Donchian channel after a macro event.

    Entry : Price breaks above/below Donchian channel post-event.
    Stop  : 1.5× ATR from entry.
    Target: 2× ATR from entry.
    """

    name: str = "EventMomentum"
    description: str = (
        "Event-driven momentum strategy: Donchian breakout after "
        "FOMC / NFP / CPI release."
    )
    applicable_regimes: list[MarketRegime] = field(
        default_factory=lambda: [MarketRegime.EVENT]
    )
    applicable_products: list[str] = field(
        default_factory=lambda: ["outright"]
    )
    priority: int = 3
    risk_multiplier: float = 0.7
    volatility_suitability: list[str] = field(
        default_factory=lambda: ["high"]
    )

    def evaluate(
        self,
        bars: list[OHLCVBar],
        indicators: dict[str, Any],
        regime: RegimeState,
    ) -> SignalParams | None:
        if regime.regime != MarketRegime.EVENT:
            return None

        donchian = indicators.get("donchian", {})
        atr = indicators.get("atr", [])

        don_upper = _last_valid(donchian.get("upper", []))
        don_lower = _last_valid(donchian.get("lower", []))
        latest_atr = _last_valid(atr)

        if any(v is None for v in [don_upper, don_lower, latest_atr]):
            return None

        if not bars:
            return None

        current_close = bars[-1].close

        # Confidence from regime confidence (proxy for event impact)
        event_confidence = min(0.85, regime.confidence * 0.9)

        # ── LONG: breakout above Donchian upper ──
        if current_close > don_upper:  # type: ignore[operator]
            entry = current_close
            stop = entry - 1.5 * latest_atr  # type: ignore[operator]
            target = entry + 2.0 * latest_atr  # type: ignore[operator]
            return SignalParams(
                direction="long",
                entry_price=entry,
                stop_price=stop,
                target_price=target,
                confidence=event_confidence,
                reason=(
                    f"Event momentum long: close {current_close:.4f} broke "
                    f"Donchian upper {don_upper:.4f}"
                ),
                risk_multiplier=self.risk_multiplier,
            )

        # ── SHORT: breakout below Donchian lower ──
        if current_close < don_lower:  # type: ignore[operator]
            entry = current_close
            stop = entry + 1.5 * latest_atr  # type: ignore[operator]
            target = entry - 2.0 * latest_atr  # type: ignore[operator]
            return SignalParams(
                direction="short",
                entry_price=entry,
                stop_price=stop,
                target_price=target,
                confidence=event_confidence,
                reason=(
                    f"Event momentum short: close {current_close:.4f} broke "
                    f"Donchian lower {don_lower:.4f}"
                ),
                risk_multiplier=self.risk_multiplier,
            )

        return None


# ══════════════════════════════════════════════════════════════════════
# 4. Event Fade
# ══════════════════════════════════════════════════════════════════════

@dataclass
class EventFade(StrategyDefinition):
    """Fade extreme event-driven moves beyond 2σ.

    Entry : Price > 2 std dev from SMA20 after event.
    Stop  : 1× ATR beyond entry.
    Target: SMA20 (mean).
    Disable: If move continues beyond 3σ.
    """

    name: str = "EventFade"
    description: str = (
        "Fade extreme event-driven moves that push price >2σ from "
        "the 20-period mean."
    )
    applicable_regimes: list[MarketRegime] = field(
        default_factory=lambda: [MarketRegime.EVENT]
    )
    applicable_products: list[str] = field(
        default_factory=lambda: ["outright"]
    )
    priority: int = 4
    risk_multiplier: float = 0.6
    volatility_suitability: list[str] = field(
        default_factory=lambda: ["high"]
    )

    def evaluate(
        self,
        bars: list[OHLCVBar],
        indicators: dict[str, Any],
        regime: RegimeState,
    ) -> SignalParams | None:
        if regime.regime != MarketRegime.EVENT:
            return None

        bollinger = indicators.get("bollinger", {})
        sma = indicators.get("sma", [])
        atr = indicators.get("atr", [])

        bb_upper = _last_valid(bollinger.get("upper", []))
        bb_lower = _last_valid(bollinger.get("lower", []))
        bb_mid = _last_valid(bollinger.get("mid", []))
        latest_sma = _last_valid(sma)
        latest_atr = _last_valid(atr)

        if any(v is None for v in [bb_upper, bb_lower, bb_mid, latest_sma, latest_atr]):
            return None

        if not bars:
            return None

        current_close = bars[-1].close

        # Compute distance from mean in std-dev units
        # Bollinger bands at 2σ: half-width = bb_upper - bb_mid
        bb_half_width = bb_upper - bb_mid  # type: ignore[operator]
        if bb_half_width <= 0:
            return None

        one_sigma = bb_half_width / 2.0  # since default Bollinger is 2σ
        distance_from_mean = abs(current_close - bb_mid)  # type: ignore[operator]
        sigma_distance = distance_from_mean / one_sigma if one_sigma > 0 else 0.0

        # Disable if beyond 3σ (move too extreme, don't fade)
        if sigma_distance > 3.0:
            logger.debug(
                "event_fade_disabled_3sigma",
                sigma_distance=sigma_distance,
            )
            return None

        # Only trigger above 2σ
        if sigma_distance < 2.0:
            return None

        # Confidence based on distance from mean (closer to 2σ = higher confidence)
        confidence = min(0.80, 0.50 + (3.0 - sigma_distance) * 0.30)

        # ── LONG fade: price far below mean ──
        if current_close < bb_lower:  # type: ignore[operator]
            entry = current_close
            stop = entry - 1.0 * latest_atr  # type: ignore[operator]
            target = latest_sma  # type: ignore[assignment]
            return SignalParams(
                direction="long",
                entry_price=entry,
                stop_price=stop,
                target_price=target,  # type: ignore[arg-type]
                confidence=confidence,
                reason=(
                    f"Event fade long: price {current_close:.4f} is "
                    f"{sigma_distance:.1f}σ below mean {bb_mid:.4f}"
                ),
                risk_multiplier=self.risk_multiplier,
            )

        # ── SHORT fade: price far above mean ──
        if current_close > bb_upper:  # type: ignore[operator]
            entry = current_close
            stop = entry + 1.0 * latest_atr  # type: ignore[operator]
            target = latest_sma  # type: ignore[assignment]
            return SignalParams(
                direction="short",
                entry_price=entry,
                stop_price=stop,
                target_price=target,  # type: ignore[arg-type]
                confidence=confidence,
                reason=(
                    f"Event fade short: price {current_close:.4f} is "
                    f"{sigma_distance:.1f}σ above mean {bb_mid:.4f}"
                ),
                risk_multiplier=self.risk_multiplier,
            )

        return None


# ══════════════════════════════════════════════════════════════════════
# 5. Volatility Fade
# ══════════════════════════════════════════════════════════════════════

@dataclass
class VolatilityFade(StrategyDefinition):
    """Fade volatility spikes at Bollinger extremes.

    Entry : Price at Bollinger extreme during volatility regime.
    Stop  : Beyond Donchian channel.
    Target: SMA20.
    Disable: During event regime.
    """

    name: str = "VolatilityFade"
    description: str = (
        "Fade volatility spikes when price reaches Bollinger extremes, "
        "targeting mean reversion to SMA20."
    )
    applicable_regimes: list[MarketRegime] = field(
        default_factory=lambda: [MarketRegime.VOLATILITY]
    )
    applicable_products: list[str] = field(
        default_factory=lambda: ["outright", "spread"]
    )
    priority: int = 5
    risk_multiplier: float = 0.7
    volatility_suitability: list[str] = field(
        default_factory=lambda: ["high"]
    )

    def evaluate(
        self,
        bars: list[OHLCVBar],
        indicators: dict[str, Any],
        regime: RegimeState,
    ) -> SignalParams | None:
        if regime.regime == MarketRegime.EVENT:
            return None
        if regime.regime != MarketRegime.VOLATILITY:
            return None

        bollinger = indicators.get("bollinger", {})
        donchian = indicators.get("donchian", {})
        sma = indicators.get("sma", [])
        atr = indicators.get("atr", [])

        bb_upper = _last_valid(bollinger.get("upper", []))
        bb_lower = _last_valid(bollinger.get("lower", []))
        don_upper = _last_valid(donchian.get("upper", []))
        don_lower = _last_valid(donchian.get("lower", []))
        latest_sma = _last_valid(sma)
        latest_atr = _last_valid(atr)

        if any(v is None for v in [bb_upper, bb_lower, don_upper, don_lower, latest_sma, latest_atr]):
            return None

        if not bars:
            return None

        current_close = bars[-1].close

        # Compute vol percentile from ATR history
        valid_atr = _last_n_valid(atr, 50)
        vol_percentile = 0.5
        if len(valid_atr) >= 10:
            arr = np.array(valid_atr)
            vol_percentile = float(np.sum(arr <= latest_atr) / len(arr))

        confidence = min(0.85, 0.50 + vol_percentile * 0.30)

        # ── LONG fade: price at lower Bollinger extreme ──
        if current_close <= bb_lower:  # type: ignore[operator]
            entry = current_close
            stop = don_lower - 0.5 * latest_atr  # type: ignore[operator]
            # Ensure stop is below entry
            if stop >= entry:
                stop = entry - 1.0 * latest_atr  # type: ignore[operator]
            target = latest_sma  # type: ignore[assignment]
            if target <= entry:  # type: ignore[operator]
                return None  # no upside
            return SignalParams(
                direction="long",
                entry_price=entry,
                stop_price=stop,
                target_price=target,  # type: ignore[arg-type]
                confidence=confidence,
                reason=(
                    f"Volatility fade long: close {current_close:.4f} at "
                    f"BB lower {bb_lower:.4f}, vol percentile {vol_percentile:.0%}"
                ),
                risk_multiplier=self.risk_multiplier,
            )

        # ── SHORT fade: price at upper Bollinger extreme ──
        if current_close >= bb_upper:  # type: ignore[operator]
            entry = current_close
            stop = don_upper + 0.5 * latest_atr  # type: ignore[operator]
            if stop <= entry:
                stop = entry + 1.0 * latest_atr  # type: ignore[operator]
            target = latest_sma  # type: ignore[assignment]
            if target >= entry:  # type: ignore[operator]
                return None  # no downside
            return SignalParams(
                direction="short",
                entry_price=entry,
                stop_price=stop,
                target_price=target,  # type: ignore[arg-type]
                confidence=confidence,
                reason=(
                    f"Volatility fade short: close {current_close:.4f} at "
                    f"BB upper {bb_upper:.4f}, vol percentile {vol_percentile:.0%}"
                ),
                risk_multiplier=self.risk_multiplier,
            )

        return None


# ══════════════════════════════════════════════════════════════════════
# 6. Curve Steepener
# ══════════════════════════════════════════════════════════════════════

@dataclass
class CurveSteepener(StrategyDefinition):
    """Spread trade: buy front / sell back when spread narrows.

    Entry : Spread narrowing toward historical low.
    Stop  : Spread tightens further by 1× ATR of spread.
    Target: Spread widens to SMA20 of spread.
    Disable: During event regime with dovish bias.
    """

    name: str = "CurveSteepener"
    description: str = (
        "Curve steepener: buy front-month / sell back-month when "
        "spread narrows toward historical low."
    )
    applicable_regimes: list[MarketRegime] = field(
        default_factory=lambda: [MarketRegime.TREND, MarketRegime.RANGE]
    )
    applicable_products: list[str] = field(
        default_factory=lambda: ["spread"]
    )
    priority: int = 6
    risk_multiplier: float = 0.9
    volatility_suitability: list[str] = field(
        default_factory=lambda: ["low", "medium"]
    )

    def evaluate(
        self,
        bars: list[OHLCVBar],
        indicators: dict[str, Any],
        regime: RegimeState,
    ) -> SignalParams | None:
        # Disable during event regime with dovish bias
        if regime.regime == MarketRegime.EVENT and regime.bias == MacroBias.DOVISH:
            return None
        if regime.regime == MarketRegime.EVENT:
            return None

        sma = indicators.get("sma", [])
        atr = indicators.get("atr", [])
        donchian = indicators.get("donchian", {})

        latest_sma = _last_valid(sma)
        latest_atr = _last_valid(atr)
        don_lower = _last_valid(donchian.get("lower", []))

        if any(v is None for v in [latest_sma, latest_atr, don_lower]):
            return None

        if len(bars) < 20:
            return None

        current_close = bars[-1].close  # spread price

        # Z-score of spread vs SMA
        closes = np.array([b.close for b in bars[-50:]], dtype=np.float64)
        spread_mean = float(np.mean(closes))
        spread_std = float(np.std(closes, ddof=1)) if len(closes) > 1 else 0.0

        if spread_std <= 0:
            return None

        z_score = (current_close - spread_mean) / spread_std

        # Steepener fires when spread is narrow (z-score negative, near historical low)
        if z_score > -1.0:
            return None  # spread not narrow enough

        # Entry: current spread level (it's narrow, we expect widening)
        entry = current_close
        # Stop: spread tightens further by 1× ATR
        stop = entry - abs(latest_atr)  # type: ignore[operator]
        # Target: SMA20 of spread
        target = latest_sma  # type: ignore[assignment]

        if target <= entry:  # type: ignore[operator]
            return None  # no widening expected

        confidence = min(0.85, 0.45 + abs(z_score) * 0.20)

        return SignalParams(
            direction="long",  # buy front, sell back → long the spread
            entry_price=entry,
            stop_price=stop,
            target_price=target,  # type: ignore[arg-type]
            confidence=confidence,
            reason=(
                f"Curve steepener: spread {current_close:.4f} narrowed "
                f"(z-score {z_score:.2f}), target SMA {latest_sma:.4f}"
            ),
            risk_multiplier=self.risk_multiplier,
        )


# ══════════════════════════════════════════════════════════════════════
# 7. Curve Flattener
# ══════════════════════════════════════════════════════════════════════

@dataclass
class CurveFlattener(StrategyDefinition):
    """Spread trade: sell front / buy back when spread widens.

    Entry : Spread widening toward historical high.
    Stop  : Spread widens further by 1× ATR of spread.
    Target: Spread narrows to SMA20 of spread.
    Disable: During event regime with hawkish bias.
    """

    name: str = "CurveFlattener"
    description: str = (
        "Curve flattener: sell front-month / buy back-month when "
        "spread widens toward historical high."
    )
    applicable_regimes: list[MarketRegime] = field(
        default_factory=lambda: [MarketRegime.TREND, MarketRegime.RANGE]
    )
    applicable_products: list[str] = field(
        default_factory=lambda: ["spread"]
    )
    priority: int = 7
    risk_multiplier: float = 0.9
    volatility_suitability: list[str] = field(
        default_factory=lambda: ["low", "medium"]
    )

    def evaluate(
        self,
        bars: list[OHLCVBar],
        indicators: dict[str, Any],
        regime: RegimeState,
    ) -> SignalParams | None:
        # Disable during event regime with hawkish bias
        if regime.regime == MarketRegime.EVENT and regime.bias == MacroBias.HAWKISH:
            return None
        if regime.regime == MarketRegime.EVENT:
            return None

        sma = indicators.get("sma", [])
        atr = indicators.get("atr", [])
        donchian = indicators.get("donchian", {})

        latest_sma = _last_valid(sma)
        latest_atr = _last_valid(atr)
        don_upper = _last_valid(donchian.get("upper", []))

        if any(v is None for v in [latest_sma, latest_atr, don_upper]):
            return None

        if len(bars) < 20:
            return None

        current_close = bars[-1].close  # spread price

        # Z-score of spread
        closes = np.array([b.close for b in bars[-50:]], dtype=np.float64)
        spread_mean = float(np.mean(closes))
        spread_std = float(np.std(closes, ddof=1)) if len(closes) > 1 else 0.0

        if spread_std <= 0:
            return None

        z_score = (current_close - spread_mean) / spread_std

        # Flattener fires when spread is wide (z-score positive, near historical high)
        if z_score < 1.0:
            return None  # spread not wide enough

        # Entry: current spread level (it's wide, we expect narrowing)
        entry = current_close
        # Stop: spread widens further by 1× ATR
        stop = entry + abs(latest_atr)  # type: ignore[operator]
        # Target: SMA20 of spread
        target = latest_sma  # type: ignore[assignment]

        if target >= entry:  # type: ignore[operator]
            return None  # no narrowing expected

        confidence = min(0.85, 0.45 + abs(z_score) * 0.20)

        return SignalParams(
            direction="short",  # sell front, buy back → short the spread
            entry_price=entry,
            stop_price=stop,
            target_price=target,  # type: ignore[arg-type]
            confidence=confidence,
            reason=(
                f"Curve flattener: spread {current_close:.4f} widened "
                f"(z-score {z_score:.2f}), target SMA {latest_sma:.4f}"
            ),
            risk_multiplier=self.risk_multiplier,
        )


# ──────────────────────────────────────────────────────────────────────
# Strategy registry
# ──────────────────────────────────────────────────────────────────────

ALL_STRATEGIES: list[StrategyDefinition] = [
    TrendFedRepricing(),
    MeanReversionRange(),
    EventMomentum(),
    EventFade(),
    VolatilityFade(),
    CurveSteepener(),
    CurveFlattener(),
]
"""All available strategies, ordered by priority (ascending = higher priority)."""


def get_strategies() -> list[StrategyDefinition]:
    """Return a copy of all registered strategies."""
    return list(ALL_STRATEGIES)
