"""Risk calculation and ladder planning models."""
from typing import Optional

from pydantic import BaseModel, Field


class LadderLevel(BaseModel):
    """Single level in a target/stop ladder."""
    level_num: int
    price: float
    ticks_from_entry: float
    pnl_per_lot: float
    lots: int = 0
    cumulative_pnl: float = 0.0


class LadderPlan(BaseModel):
    """Complete ladder plan for entries, stops, or targets."""
    levels: list[LadderLevel] = Field(default_factory=list)
    total_lots: int = 0
    weighted_avg_price: float = 0.0


class PositionSizing(BaseModel):
    """Position sizing recommendation."""
    base_lots: int
    volatility_adjusted_lots: int
    max_allowed_lots: int
    risk_per_lot: float
    total_risk_usd: float
    slippage_estimate_usd: float
    commission_estimate_usd: float
    net_risk_usd: float


class RiskProfile(BaseModel):
    """Complete risk profile for a trade plan."""
    symbol: str
    direction: str
    entry_price: float
    stop_price: float
    target_price: float
    tick_size: float
    tick_value: float
    risk_ticks: float
    reward_ticks: float
    risk_reward_ratio: float
    sizing: Optional[PositionSizing] = None
    entry_ladder: Optional[LadderPlan] = None
    stop_ladder: Optional[LadderPlan] = None
    target_ladder: Optional[LadderPlan] = None


class TradeRiskAssessment(BaseModel):
    """Full risk assessment combining risk profile with market context."""
    risk_profile: RiskProfile
    current_atr: Optional[float] = None
    atr_multiple_risk: Optional[float] = None
    atr_multiple_reward: Optional[float] = None
    regime: str = ""
    macro_bias: str = ""
    volatility_percentile: Optional[float] = None
    warnings: list[str] = Field(default_factory=list)
