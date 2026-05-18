"""
Execution input contracts — risk parameters and account configuration.

These are planning-only contracts for sizing, stop, and target computation.
NOT for order submission or execution routing.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.contracts.market_data import ContractType


# ── Account Configuration ─────────────────────────────────────

class AccountConfig(BaseModel):
    """Trader account configuration for risk computations."""
    max_risk_per_trade: float = Field(default=500.0, gt=0)
    max_lots: int = Field(default=20, ge=1)
    max_daily_risk: float = Field(default=2500.0, gt=0)
    event_risk_multiplier: float = Field(default=0.5, gt=0, le=1.0)
    default_slippage_ticks: int = Field(default=1, ge=0)
    default_commission_per_lot: float = Field(default=2.50, ge=0)


# ── Risk Calculation Input ────────────────────────────────────

class RiskCalcInput(BaseModel):
    """Input for risk/sizing computation."""
    entry_price: float = Field(gt=0)
    stop_price: float = Field(gt=0)
    contract_type: ContractType = ContractType.OUTRIGHT
    tick_size: float = Field(gt=0)
    tick_value: float = Field(gt=0)
    is_event_regime: bool = False
    volatility_multiplier: float = Field(default=1.0, ge=0)
    custom_max_risk: Optional[float] = None
    custom_max_lots: Optional[int] = None


# ── Risk Calculation Result ───────────────────────────────────

class RiskCalcResult(BaseModel):
    """Output from risk calculation."""
    stop_distance_ticks: float = Field(ge=0)
    stop_distance_price: float = Field(ge=0)
    dollar_risk_per_lot: float = Field(ge=0)
    max_lots: int = Field(ge=0)
    total_risk: float = Field(ge=0)
    commission_per_lot: float = Field(ge=0)
    total_commission: float = Field(ge=0)
    slippage_per_lot: float = Field(ge=0)
    total_slippage: float = Field(ge=0)
    round_trip_cost: float = Field(ge=0)
    risk_reward_ratio: Optional[float] = None
    effective_max_risk: float = Field(ge=0)
    event_adjusted: bool = False
    caution_flags: list[str] = Field(default_factory=list)


# ── Scale Level ───────────────────────────────────────────────

class ScaleLevel(BaseModel):
    """Entry or exit scale level for ladder planning."""
    level_index: int = Field(ge=0)
    price: float = Field(gt=0)
    lots: int = Field(ge=1)
    ratio: float = Field(ge=0, le=1.0)
    dollar_risk: float = Field(ge=0)
    description: str = ""


# ── Ladder Plan ───────────────────────────────────────────────

class LadderPlan(BaseModel):
    """Complete entry/exit ladder plan."""
    entry_levels: list[ScaleLevel] = Field(default_factory=list)
    target_levels: list[ScaleLevel] = Field(default_factory=list)
    stop_price: float = Field(gt=0)
    total_lots: int = Field(ge=0)
    total_risk: float = Field(ge=0)
    average_entry: float = Field(ge=0)
    risk_reward_ratio: Optional[float] = None
