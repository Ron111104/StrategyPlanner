"""Adaptive strategy ladder models."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AdaptiveLadderLevel(BaseModel):
    """Single level in an adaptive strategy ladder."""
    level: int
    entry_price: float
    entry_bp: Optional[float] = None
    lots: int
    cumulative_lots: int = 0
    distance_from_ref: float = 0.0
    distance_ticks: float = 0.0
    risk_usd: float = 0.0


class AdaptiveLadder(BaseModel):
    """Complete adaptive strategy ladder generated dynamically."""
    strategy: str
    symbol: str
    product_key: str
    timeframe: str
    direction: str
    instrument_type: str  # "outright" or "spread"
    regime: str
    macro_bias: str

    entry_reference: float
    entry_reference_bp: Optional[float] = None
    levels: list[AdaptiveLadderLevel] = Field(default_factory=list)
    total_lots: int = 0
    avg_entry: float = 0.0
    avg_entry_bp: Optional[float] = None

    stop: float = 0.0
    stop_bp: Optional[float] = None
    stop_distance_ticks: float = 0.0

    target_1: float = 0.0
    target_1_bp: Optional[float] = None
    target_2: Optional[float] = None
    target_2_bp: Optional[float] = None

    risk_reward: float = 0.0
    total_risk_usd: float = 0.0
    total_reward_usd: float = 0.0

    spacing_method: str = ""
    spacing_value: float = 0.0
    confidence: float = 0.0

    atr_at_generation: Optional[float] = None
    dcw_at_generation: Optional[float] = None
    vol_percentile: Optional[float] = None
    mtf_alignment: Optional[float] = None

    notes: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class LadderRequest(BaseModel):
    """Request to generate an adaptive strategy ladder."""
    product_key: str
    symbol: str
    timeframe: str
    strategy: str
    direction: Optional[str] = None
    max_levels: int = 5
    max_lots: Optional[int] = None
    max_risk_usd: Optional[float] = None


class LadderResponse(BaseModel):
    """Response from ladder generation."""
    success: bool
    ladder: Optional[AdaptiveLadder] = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
