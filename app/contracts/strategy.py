"""Strategy definition and evaluation models."""
from typing import Optional

from pydantic import BaseModel, Field

from app.contracts.signals import StrategySignal


class StrategyDefinition(BaseModel):
    """Definition of a strategy from configuration."""
    name: str
    enabled: bool = True
    priority: int = 99
    applicable_regimes: list[str] = Field(default_factory=list)
    applicable_timeframes: list[str] = Field(default_factory=list)
    min_confidence: float = 0.5
    spread_only: bool = False


class EntryExitPlan(BaseModel):
    """Planned entry and exit levels."""
    symbol: str
    strategy_name: str
    direction: str
    entry_price: float
    stop_price: float
    primary_target: float
    secondary_target: Optional[float] = None
    tertiary_target: Optional[float] = None
    risk_ticks: float
    reward_ticks: float
    risk_reward_ratio: float
    confidence: float
    rationale: str = ""


class StrategyEvalRequest(BaseModel):
    """Internal request to evaluate a strategy."""
    strategy_name: str
    symbol: str
    product_key: str
    timeframe: str
    instrument_type: str  # "outright" or "spread"


class StrategyEvalResult(BaseModel):
    """Result of evaluating multiple strategies."""
    symbol: str
    product_key: str
    timeframe: str
    regime: str
    macro_bias: str
    signals: list[StrategySignal] = Field(default_factory=list)
    entry_exit_plans: list[EntryExitPlan] = Field(default_factory=list)
    best_opportunity: Optional[StrategySignal] = None
    evaluated_strategies: list[str] = Field(default_factory=list)
    skipped_strategies: list[str] = Field(default_factory=list)
