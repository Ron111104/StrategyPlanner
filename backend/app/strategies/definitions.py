"""
Strategy Definitions — six institutional strategies for Fed Funds futures.

Each strategy contains complete logic for:
- regime applicability
- entry/stop/target logic
- confidence scoring
- disable conditions
- invalidation conditions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from app.contracts.macro_inputs import MarketRegime
from app.contracts.market_data import ContractType
from app.services.indicator_engine import IndicatorResult


class StrategyName(str, Enum):
    TREND_FED_REPRICING = "TrendFedRepricing"
    MEAN_REVERSION_RANGE = "MeanReversionRange"
    EVENT_MOMENTUM = "EventMomentum"
    EVENT_FADE = "EventFade"
    VOLATILITY_FADE = "VolatilityFade"
    CURVE_STEEPENER = "CurveSteepener"
    CURVE_FLATTENER = "CurveFlattener"


@dataclass
class StrategyDefinition:
    """Complete strategy definition with all parameters."""
    name: StrategyName
    regime_applicability: list[MarketRegime]
    contract_types: list[ContractType]
    priority: int
    risk_multiplier: float = 1.0
    volatility_suitability: str = "normal"
    description: str = ""


@dataclass
class StrategyEvaluation:
    """Result of evaluating a single strategy against market data."""
    strategy_name: str
    is_applicable: bool = False
    direction: str = "neutral"
    entry_price: float = 0.0
    stop_price: float = 0.0
    targets: list[float] = field(default_factory=list)
    confidence: float = 0.0
    trigger_conditions: list[str] = field(default_factory=list)
    disable_conditions: list[str] = field(default_factory=list)
    invalidation_conditions: list[str] = field(default_factory=list)
    caution_reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Strategy Definitions ──────────────────────────────────────

STRATEGY_REGISTRY: dict[StrategyName, StrategyDefinition] = {
    StrategyName.TREND_FED_REPRICING: StrategyDefinition(
        name=StrategyName.TREND_FED_REPRICING,
        regime_applicability=[MarketRegime.TREND],
        contract_types=[ContractType.OUTRIGHT, ContractType.SPREAD],
        priority=1,
        risk_multiplier=1.0,
        volatility_suitability="normal",
        description="Breakout continuation on repricing momentum",
    ),
    StrategyName.MEAN_REVERSION_RANGE: StrategyDefinition(
        name=StrategyName.MEAN_REVERSION_RANGE,
        regime_applicability=[MarketRegime.RANGE],
        contract_types=[ContractType.OUTRIGHT, ContractType.SPREAD],
        priority=2,
        risk_multiplier=0.8,
        volatility_suitability="low",
        description="Range fade on Donchian reversion",
    ),
    StrategyName.EVENT_MOMENTUM: StrategyDefinition(
        name=StrategyName.EVENT_MOMENTUM,
        regime_applicability=[MarketRegime.EVENT],
        contract_types=[ContractType.OUTRIGHT],
        priority=3,
        risk_multiplier=1.2,
        volatility_suitability="high",
        description="Macro event breakout continuation",
    ),
    StrategyName.EVENT_FADE: StrategyDefinition(
        name=StrategyName.EVENT_FADE,
        regime_applicability=[MarketRegime.EVENT],
        contract_types=[ContractType.OUTRIGHT],
        priority=4,
        risk_multiplier=0.7,
        volatility_suitability="high",
        description="Post-event exhaustion fade",
    ),
    StrategyName.VOLATILITY_FADE: StrategyDefinition(
        name=StrategyName.VOLATILITY_FADE,
        regime_applicability=[MarketRegime.VOLATILITY],
        contract_types=[ContractType.OUTRIGHT, ContractType.SPREAD],
        priority=5,
        risk_multiplier=0.6,
        volatility_suitability="high",
        description="High ATR mean reversion fade",
    ),
    StrategyName.CURVE_STEEPENER: StrategyDefinition(
        name=StrategyName.CURVE_STEEPENER,
        regime_applicability=[MarketRegime.TREND, MarketRegime.RANGE, MarketRegime.VOLATILITY],
        contract_types=[ContractType.SPREAD],
        priority=6,
        risk_multiplier=1.0,
        volatility_suitability="normal",
        description="Spread widening on lower Donchian break",
    ),
    StrategyName.CURVE_FLATTENER: StrategyDefinition(
        name=StrategyName.CURVE_FLATTENER,
        regime_applicability=[MarketRegime.TREND, MarketRegime.RANGE, MarketRegime.VOLATILITY],
        contract_types=[ContractType.SPREAD],
        priority=7,
        risk_multiplier=1.0,
        volatility_suitability="normal",
        description="Spread compression on upper Donchian break",
    ),
}


# ── Strategy Logic Functions ──────────────────────────────────

def evaluate_trend_fed_repricing(
    indicators: IndicatorResult,
    price: float,
    atr: float,
) -> StrategyEvaluation:
    """TrendFedRepricing: breakout continuation, momentum-based, trend regime only."""
    eval_result = StrategyEvaluation(strategy_name=StrategyName.TREND_FED_REPRICING.value)

    if not indicators.is_valid or not indicators.sma_fast or not indicators.sma_slow:
        eval_result.disable_conditions.append("Invalid indicators")
        return eval_result

    sma_fast = indicators.sma_fast[-1]
    sma_slow = indicators.sma_slow[-1]
    donchian_upper = indicators.current_donchian_upper
    donchian_lower = indicators.current_donchian_lower

    if atr == 0:
        eval_result.disable_conditions.append("Zero ATR")
        return eval_result

    # Bullish breakout: price > Donchian upper AND fast > slow
    if price >= donchian_upper and sma_fast > sma_slow:
        eval_result.is_applicable = True
        eval_result.direction = "long"
        eval_result.entry_price = price
        eval_result.stop_price = round(price - 2 * atr, 6)
        eval_result.targets = [
            round(price + 1.5 * atr, 6),
            round(price + 2.5 * atr, 6),
            round(price + 4.0 * atr, 6),
        ]
        eval_result.confidence = min(0.85, 0.5 + (sma_fast - sma_slow) / price * 10)
        eval_result.trigger_conditions = [
            f"Price ({price:.3f}) >= Donchian upper ({donchian_upper:.3f})",
            f"SMA fast ({sma_fast:.3f}) > SMA slow ({sma_slow:.3f})",
        ]

    # Bearish breakout: price < Donchian lower AND fast < slow
    elif price <= donchian_lower and sma_fast < sma_slow:
        eval_result.is_applicable = True
        eval_result.direction = "short"
        eval_result.entry_price = price
        eval_result.stop_price = round(price + 2 * atr, 6)
        eval_result.targets = [
            round(price - 1.5 * atr, 6),
            round(price - 2.5 * atr, 6),
            round(price - 4.0 * atr, 6),
        ]
        eval_result.confidence = min(0.85, 0.5 + (sma_slow - sma_fast) / price * 10)
        eval_result.trigger_conditions = [
            f"Price ({price:.3f}) <= Donchian lower ({donchian_lower:.3f})",
            f"SMA fast ({sma_fast:.3f}) < SMA slow ({sma_slow:.3f})",
        ]

    eval_result.invalidation_conditions = [
        "MA crossover reversal",
        "ATR collapse below 50th percentile",
    ]

    return eval_result


def evaluate_mean_reversion_range(
    indicators: IndicatorResult,
    price: float,
    atr: float,
) -> StrategyEvaluation:
    """MeanReversionRange: range fade, Donchian reversion, low volatility."""
    eval_result = StrategyEvaluation(strategy_name=StrategyName.MEAN_REVERSION_RANGE.value)

    if not indicators.is_valid:
        eval_result.disable_conditions.append("Invalid indicators")
        return eval_result

    donchian_upper = indicators.current_donchian_upper
    donchian_lower = indicators.current_donchian_lower
    donchian_mid = indicators.donchian_mid[-1] if indicators.donchian_mid else price

    if atr == 0:
        eval_result.disable_conditions.append("Zero ATR")
        return eval_result

    # Fade upper Donchian
    if price >= donchian_upper * 0.998:
        eval_result.is_applicable = True
        eval_result.direction = "short"
        eval_result.entry_price = price
        eval_result.stop_price = round(price + 1.5 * atr, 6)
        eval_result.targets = [
            donchian_mid,
            round(donchian_lower + (donchian_upper - donchian_lower) * 0.3, 6),
            donchian_lower,
        ]
        eval_result.confidence = 0.6
        eval_result.trigger_conditions = [
            f"Price ({price:.3f}) near Donchian upper ({donchian_upper:.3f})",
            "Low volatility range regime",
        ]

    # Fade lower Donchian
    elif price <= donchian_lower * 1.002:
        eval_result.is_applicable = True
        eval_result.direction = "long"
        eval_result.entry_price = price
        eval_result.stop_price = round(price - 1.5 * atr, 6)
        eval_result.targets = [
            donchian_mid,
            round(donchian_upper - (donchian_upper - donchian_lower) * 0.3, 6),
            donchian_upper,
        ]
        eval_result.confidence = 0.6
        eval_result.trigger_conditions = [
            f"Price ({price:.3f}) near Donchian lower ({donchian_lower:.3f})",
            "Low volatility range regime",
        ]

    eval_result.invalidation_conditions = [
        "Breakout beyond Donchian + 1 ATR",
        "Regime shift to trend",
    ]

    return eval_result


def evaluate_event_momentum(
    indicators: IndicatorResult,
    price: float,
    atr: float,
) -> StrategyEvaluation:
    """EventMomentum: macro event breakout continuation, volatility expansion."""
    eval_result = StrategyEvaluation(strategy_name=StrategyName.EVENT_MOMENTUM.value)

    if not indicators.is_valid:
        eval_result.disable_conditions.append("Invalid indicators")
        return eval_result

    bb_upper = indicators.bollinger_upper[-1] if indicators.bollinger_upper else 0
    bb_lower = indicators.bollinger_lower[-1] if indicators.bollinger_lower else 0

    if atr == 0:
        eval_result.disable_conditions.append("Zero ATR")
        return eval_result

    # Bullish breakout beyond upper Bollinger
    if price > bb_upper and bb_upper > 0:
        eval_result.is_applicable = True
        eval_result.direction = "long"
        eval_result.entry_price = price
        eval_result.stop_price = round(price - 2.5 * atr, 6)
        eval_result.targets = [
            round(price + 2 * atr, 6),
            round(price + 3.5 * atr, 6),
            round(price + 5 * atr, 6),
        ]
        eval_result.confidence = 0.7
        eval_result.trigger_conditions = [
            f"Price ({price:.3f}) > Bollinger upper ({bb_upper:.3f})",
            "Event regime active",
        ]

    # Bearish breakout beyond lower Bollinger
    elif price < bb_lower and bb_lower > 0:
        eval_result.is_applicable = True
        eval_result.direction = "short"
        eval_result.entry_price = price
        eval_result.stop_price = round(price + 2.5 * atr, 6)
        eval_result.targets = [
            round(price - 2 * atr, 6),
            round(price - 3.5 * atr, 6),
            round(price - 5 * atr, 6),
        ]
        eval_result.confidence = 0.7
        eval_result.trigger_conditions = [
            f"Price ({price:.3f}) < Bollinger lower ({bb_lower:.3f})",
            "Event regime active",
        ]

    eval_result.invalidation_conditions = [
        "Price reversal back inside Bollinger bands",
        "Volume collapse post-event",
    ]

    return eval_result


def evaluate_event_fade(
    indicators: IndicatorResult,
    price: float,
    atr: float,
) -> StrategyEvaluation:
    """EventFade: post-event exhaustion fade, ATR exhaustion logic."""
    eval_result = StrategyEvaluation(strategy_name=StrategyName.EVENT_FADE.value)

    if not indicators.is_valid:
        eval_result.disable_conditions.append("Invalid indicators")
        return eval_result

    if atr == 0:
        eval_result.disable_conditions.append("Zero ATR")
        return eval_result

    bb_upper = indicators.bollinger_upper[-1] if indicators.bollinger_upper else 0
    bb_lower = indicators.bollinger_lower[-1] if indicators.bollinger_lower else 0
    bb_mid = indicators.bollinger_mid[-1] if indicators.bollinger_mid else price

    # Exhaustion at upper extreme (fade short)
    if price > bb_upper * 1.005 and bb_upper > 0:
        eval_result.is_applicable = True
        eval_result.direction = "short"
        eval_result.entry_price = price
        eval_result.stop_price = round(price + 1.5 * atr, 6)
        eval_result.targets = [
            bb_upper,
            bb_mid,
            round(bb_mid - 0.5 * (bb_upper - bb_mid), 6),
        ]
        eval_result.confidence = 0.55
        eval_result.trigger_conditions = [
            f"Exhaustion: price ({price:.3f}) > 1.005 * BB upper ({bb_upper:.3f})",
            "ATR elevated (post-event)",
        ]

    # Exhaustion at lower extreme (fade long)
    elif price < bb_lower * 0.995 and bb_lower > 0:
        eval_result.is_applicable = True
        eval_result.direction = "long"
        eval_result.entry_price = price
        eval_result.stop_price = round(price - 1.5 * atr, 6)
        eval_result.targets = [
            bb_lower,
            bb_mid,
            round(bb_mid + 0.5 * (bb_mid - bb_lower), 6),
        ]
        eval_result.confidence = 0.55
        eval_result.trigger_conditions = [
            f"Exhaustion: price ({price:.3f}) < 0.995 * BB lower ({bb_lower:.3f})",
            "ATR elevated (post-event)",
        ]

    eval_result.invalidation_conditions = [
        "Continued momentum beyond 3 ATR",
        "New event catalyst",
    ]
    eval_result.caution_reasons.append("Counter-trend — reduced sizing recommended")

    return eval_result


def evaluate_volatility_fade(
    indicators: IndicatorResult,
    price: float,
    atr: float,
) -> StrategyEvaluation:
    """VolatilityFade: high ATR mean reversion, volatility normalization."""
    eval_result = StrategyEvaluation(strategy_name=StrategyName.VOLATILITY_FADE.value)

    if not indicators.is_valid:
        eval_result.disable_conditions.append("Invalid indicators")
        return eval_result

    if atr == 0:
        eval_result.disable_conditions.append("Zero ATR")
        return eval_result

    sma_slow = indicators.sma_slow[-1] if indicators.sma_slow else price

    # Price extended above mean — fade short
    if price > sma_slow + 2 * atr:
        eval_result.is_applicable = True
        eval_result.direction = "short"
        eval_result.entry_price = price
        eval_result.stop_price = round(price + 1.5 * atr, 6)
        eval_result.targets = [
            round(sma_slow + atr, 6),
            sma_slow,
            round(sma_slow - 0.5 * atr, 6),
        ]
        eval_result.confidence = 0.5
        eval_result.trigger_conditions = [
            f"Price ({price:.3f}) > SMA slow + 2*ATR ({sma_slow + 2 * atr:.3f})",
            "High volatility regime",
        ]

    # Price extended below mean — fade long
    elif price < sma_slow - 2 * atr:
        eval_result.is_applicable = True
        eval_result.direction = "long"
        eval_result.entry_price = price
        eval_result.stop_price = round(price - 1.5 * atr, 6)
        eval_result.targets = [
            round(sma_slow - atr, 6),
            sma_slow,
            round(sma_slow + 0.5 * atr, 6),
        ]
        eval_result.confidence = 0.5
        eval_result.trigger_conditions = [
            f"Price ({price:.3f}) < SMA slow - 2*ATR ({sma_slow - 2 * atr:.3f})",
            "High volatility regime",
        ]

    eval_result.invalidation_conditions = [
        "Trend confirmation (MA crossover in same direction)",
        "Continued volatility expansion",
    ]
    eval_result.caution_reasons.append("Mean reversion in high vol — tight sizing required")

    return eval_result


def evaluate_curve_steepener(
    indicators: IndicatorResult,
    spread_bp: float,
    atr: float,
) -> StrategyEvaluation:
    """
    CurveSteepener: spread widening logic.
    below lower Donchian AND delta < -1 ATR
    """
    eval_result = StrategyEvaluation(strategy_name=StrategyName.CURVE_STEEPENER.value)

    if not indicators.is_valid:
        eval_result.disable_conditions.append("Invalid indicators")
        return eval_result

    if atr == 0:
        eval_result.disable_conditions.append("Zero ATR")
        return eval_result

    donchian_lower = indicators.current_donchian_lower
    donchian_upper = indicators.current_donchian_upper
    donchian_mid = indicators.donchian_mid[-1] if indicators.donchian_mid else spread_bp

    delta = indicators.spread_delta[-1] if indicators.spread_delta else 0.0

    # Steepener: below lower Donchian AND delta < -1 ATR
    if spread_bp <= donchian_lower and delta < -atr:
        eval_result.is_applicable = True
        eval_result.direction = "short"  # selling spread = steepener
        eval_result.entry_price = spread_bp
        eval_result.stop_price = round(spread_bp + 2 * atr, 4)
        eval_result.targets = [
            round(spread_bp - 1.5 * atr, 4),
            round(spread_bp - 2.5 * atr, 4),
            round(spread_bp - 4 * atr, 4),
        ]
        eval_result.confidence = 0.65
        eval_result.trigger_conditions = [
            f"Spread ({spread_bp:.1f} bp) <= Donchian lower ({donchian_lower:.1f} bp)",
            f"Delta ({delta:.2f}) < -1 ATR ({-atr:.2f})",
        ]
        eval_result.metadata = {"delta": delta, "donchian_lower": donchian_lower}

    eval_result.invalidation_conditions = [
        "Spread reversal above Donchian mid",
        "Delta reversal to positive",
    ]

    return eval_result


def evaluate_curve_flattener(
    indicators: IndicatorResult,
    spread_bp: float,
    atr: float,
) -> StrategyEvaluation:
    """
    CurveFlattener: spread compression logic.
    above upper Donchian AND delta > +1 ATR
    """
    eval_result = StrategyEvaluation(strategy_name=StrategyName.CURVE_FLATTENER.value)

    if not indicators.is_valid:
        eval_result.disable_conditions.append("Invalid indicators")
        return eval_result

    if atr == 0:
        eval_result.disable_conditions.append("Zero ATR")
        return eval_result

    donchian_upper = indicators.current_donchian_upper
    donchian_lower = indicators.current_donchian_lower
    donchian_mid = indicators.donchian_mid[-1] if indicators.donchian_mid else spread_bp

    delta = indicators.spread_delta[-1] if indicators.spread_delta else 0.0

    # Flattener: above upper Donchian AND delta > +1 ATR
    if spread_bp >= donchian_upper and delta > atr:
        eval_result.is_applicable = True
        eval_result.direction = "long"  # buying spread = flattener
        eval_result.entry_price = spread_bp
        eval_result.stop_price = round(spread_bp - 2 * atr, 4)
        eval_result.targets = [
            round(spread_bp + 1.5 * atr, 4),
            round(spread_bp + 2.5 * atr, 4),
            round(spread_bp + 4 * atr, 4),
        ]
        eval_result.confidence = 0.65
        eval_result.trigger_conditions = [
            f"Spread ({spread_bp:.1f} bp) >= Donchian upper ({donchian_upper:.1f} bp)",
            f"Delta ({delta:.2f}) > +1 ATR ({atr:.2f})",
        ]
        eval_result.metadata = {"delta": delta, "donchian_upper": donchian_upper}

    eval_result.invalidation_conditions = [
        "Spread reversal below Donchian mid",
        "Delta reversal to negative",
    ]

    return eval_result


# ── Evaluator Registry ────────────────────────────────────────

STRATEGY_EVALUATORS = {
    StrategyName.TREND_FED_REPRICING: evaluate_trend_fed_repricing,
    StrategyName.MEAN_REVERSION_RANGE: evaluate_mean_reversion_range,
    StrategyName.EVENT_MOMENTUM: evaluate_event_momentum,
    StrategyName.EVENT_FADE: evaluate_event_fade,
    StrategyName.VOLATILITY_FADE: evaluate_volatility_fade,
    StrategyName.CURVE_STEEPENER: evaluate_curve_steepener,
    StrategyName.CURVE_FLATTENER: evaluate_curve_flattener,
}
