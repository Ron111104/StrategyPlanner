"""Regime and macro bias models."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class RegimeType(str, Enum):
    TREND = "trend"
    RANGE = "range"
    VOLATILITY = "volatility"
    EVENT = "event"


class MacroBias(str, Enum):
    HAWKISH = "hawkish"
    DOVISH = "dovish"
    NEUTRAL = "neutral"


class RegimeState(BaseModel):
    """Current regime state set by the trader."""
    regime: RegimeType = RegimeType.RANGE
    macro_bias: MacroBias = MacroBias.NEUTRAL
    notes: str = ""
    updated_at: datetime = Field(default_factory=datetime.utcnow)
