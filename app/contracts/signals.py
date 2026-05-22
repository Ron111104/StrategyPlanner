"""Signal and strategy signal models."""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SignalDirection(str, Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class SignalStrength(str, Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class Signal(BaseModel):
    """Base signal model."""
    direction: SignalDirection = SignalDirection.FLAT
    strength: SignalStrength = SignalStrength.NEUTRAL
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class StrategySignal(Signal):
    """Signal produced by a strategy evaluation."""
    strategy_name: str
    symbol: str
    timeframe: str
    entry_price: Optional[float] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    rationale: str = ""
    regime: str = ""
    macro_bias: str = ""


class SignalCard(BaseModel):
    """Aggregated signal card for the dashboard."""
    symbol: str
    product_key: str
    instrument_type: str  # "outright" or "spread"
    signals: list[StrategySignal] = Field(default_factory=list)
    best_signal: Optional[StrategySignal] = None
    overall_direction: SignalDirection = SignalDirection.FLAT
    overall_confidence: float = 0.0
    last_price: Optional[float] = None
    spread_bp: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
