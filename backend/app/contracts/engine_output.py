"""
Engine output contracts — strategy signals, evaluation results, and responses.

All strategy engine outputs are typed through these contracts.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.contracts.execution_inputs import LadderPlan, RiskCalcResult, ScaleLevel
from app.contracts.macro_inputs import MacroBias, MarketRegime, RegimeState
from app.contracts.market_data import ContractType, Timeframe


# ── Signal Direction ──────────────────────────────────────────

class SignalDirection(str, Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


# ── Strategy Signal ───────────────────────────────────────────

class StrategySignal(BaseModel):
    """Complete strategy signal output with all context."""

    # ── Identity ──────────────────────────────────────────────
    signal_id: str
    strategy_name: str
    product: str
    contract_type: ContractType
    timeframe: Timeframe
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    # ── Signal Core ───────────────────────────────────────────
    direction: SignalDirection
    entry_price: float = Field(gt=0)
    stop_price: float = Field(gt=0)
    targets: list[float] = Field(min_length=1)

    # ── Risk Profile ─────────────────────────────────────────
    risk_calc: RiskCalcResult
    ladder_plan: Optional[LadderPlan] = None

    # ── Scoring ───────────────────────────────────────────────
    confidence_score: float = Field(ge=0, le=1.0)
    priority: int = Field(ge=0, default=0)
    caution_flag: bool = False
    caution_reasons: list[str] = Field(default_factory=list)

    # ── Trigger & Disable Conditions ─────────────────────────
    trigger_conditions: list[str] = Field(default_factory=list)
    disable_conditions_checked: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)

    # ── Regime & Macro Context ────────────────────────────────
    regime_context: RegimeState
    macro_bias: MacroBias = MacroBias.NEUTRAL

    # ── Strategy Metadata ─────────────────────────────────────
    strategy_metadata: dict[str, Any] = Field(default_factory=dict)


# ── No Signal Response ────────────────────────────────────────

class NoSignalResponse(BaseModel):
    """Structured response when no signal is generated."""
    product: str
    timeframe: Timeframe
    reason: str
    regime: MarketRegime
    macro_bias: MacroBias
    checks_performed: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Strategy Evaluate Request ─────────────────────────────────

class StrategyEvaluateRequest(BaseModel):
    """Request to evaluate strategies for a product."""
    product: str = Field(min_length=1)
    timeframe: Timeframe = Timeframe.H1
    strategies: Optional[list[str]] = None  # None = all strategies
    regime_override: Optional[MarketRegime] = None
    macro_bias_override: Optional[MacroBias] = None
    max_signals: int = Field(default=5, ge=1, le=20)


# ── Strategy Evaluate Response ────────────────────────────────

class StrategyEvaluateResponse(BaseModel):
    """Response from strategy evaluation containing all signals."""
    product: str
    timeframe: Timeframe
    regime: RegimeState
    signals: list[StrategySignal] = Field(default_factory=list)
    no_signal_reasons: list[NoSignalResponse] = Field(default_factory=list)
    evaluation_time_ms: float = Field(ge=0)
    strategies_evaluated: list[str] = Field(default_factory=list)
    conflicting_strategies: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
