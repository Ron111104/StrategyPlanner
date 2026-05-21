"""Engine output contract models for ZQ Strategy Planning Platform.

Defines strategy signal models, evaluation request/response schemas,
and no-signal reason models returned by the strategy evaluation engine.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.contracts.execution_inputs import AccountConfig, LadderPlan
from app.contracts.macro_inputs import MacroBias, MarketRegime, RegimeState
from app.contracts.market_data import Timeframe


class SignalDirection(StrEnum):
    """Trade signal direction."""

    LONG = "long"
    SHORT = "short"


class SignalStrength(StrEnum):
    """Confidence-based signal strength classification."""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


class StrategySignal(BaseModel):
    """A concrete trade signal produced by the strategy engine.

    Contains the full trade plan including entry, stop, target, sizing,
    regime context, indicators used, and optional ladder plan.
    """

    strategy_name: Annotated[str, Field(min_length=1, description="Name of the strategy that generated this signal")]
    product: Annotated[str, Field(min_length=1, description="Product symbol")]
    direction: SignalDirection
    entry_price: Annotated[float, Field(gt=0, description="Recommended entry price")]
    stop_price: Annotated[float, Field(gt=0, description="Recommended stop price")]
    target_price: Annotated[float, Field(gt=0, description="Recommended target price")]
    confidence: Annotated[float, Field(ge=0.0, le=1.0, description="Signal confidence 0-1")]
    strength: SignalStrength
    regime: MarketRegime
    bias: MacroBias
    risk_reward_ratio: Annotated[float, Field(ge=0, description="Reward-to-risk ratio")]
    dollar_risk: Annotated[float, Field(ge=0, description="Dollar risk for this signal")]
    position_size: Annotated[int, Field(gt=0, description="Recommended position size")]
    timestamp: datetime
    invalidation_conditions: list[str] = Field(
        default_factory=list,
        description="Conditions that would invalidate this signal",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Additional notes or context for the trader",
    )
    ladder: LadderPlan | None = None
    indicators_used: dict[str, float] = Field(
        default_factory=dict,
        description="Indicator name -> value mapping used in signal generation",
    )

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        """Clamp confidence to [0.0, 1.0]."""
        return max(0.0, min(1.0, v))


class NoSignalResponse(BaseModel):
    """Returned when no valid signal is generated for a product.

    Includes the reason why no signal was found and which strategies
    were evaluated.
    """

    product: Annotated[str, Field(min_length=1)]
    reason: Annotated[str, Field(min_length=1, description="Explanation of why no signal was generated")]
    regime: MarketRegime
    bias: MacroBias
    timestamp: datetime
    strategies_evaluated: list[str] = Field(
        default_factory=list,
        description="List of strategy names that were evaluated",
    )


class StrategyEvaluateRequest(BaseModel):
    """Request to evaluate strategies for a given product and timeframe."""

    product: Annotated[str, Field(min_length=1, description="Product symbol to evaluate")]
    timeframe: Timeframe
    regime_override: MarketRegime | None = None
    bias_override: MacroBias | None = None
    account_config: AccountConfig | None = None


class StrategyEvaluateResponse(BaseModel):
    """Response from the strategy evaluation engine.

    Contains any generated signals, reasons for no-signals,
    the regime state, and evaluation metadata.
    """

    product: Annotated[str, Field(min_length=1)]
    timeframe: Timeframe
    signals: list[StrategySignal] = Field(default_factory=list)
    no_signal_reasons: list[NoSignalResponse] = Field(default_factory=list)
    regime: RegimeState
    evaluation_time_ms: Annotated[float, Field(ge=0, description="Time taken for evaluation in milliseconds")]
    bars_analyzed: Annotated[int, Field(ge=0, description="Number of bars analyzed")]
    timestamp: datetime
