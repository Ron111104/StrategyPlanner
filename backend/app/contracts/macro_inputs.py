"""
Macro inputs and regime domain contracts.

Defines regime classification, macro bias, event windows,
and all regime-related typed schemas.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Regime Enums ──────────────────────────────────────────────

class MarketRegime(str, Enum):
    """
    Supported market regimes.
    Priority order: event → volatility → trend → range → no_signal
    """
    EVENT = "event"
    VOLATILITY = "volatility"
    TREND = "trend"
    RANGE = "range"
    NO_SIGNAL = "no_signal"


class MacroBias(str, Enum):
    """Macro directional bias set by trader."""
    HAWKISH = "hawkish"
    DOVISH = "dovish"
    NEUTRAL = "neutral"


# ── Macro Event ───────────────────────────────────────────────

class MacroEvent(BaseModel):
    """Scheduled macro event with impact window."""
    event_id: str
    name: str = Field(min_length=1)
    scheduled_time: datetime
    impact: str = Field(default="high", pattern=r"^(low|medium|high|critical)$")
    description: Optional[str] = None
    lock_window_hours: float = Field(default=4.0, ge=0)
    volatility_override: Optional[float] = Field(default=None, ge=0)


# ── Regime State ──────────────────────────────────────────────

class RegimeState(BaseModel):
    """Current regime classification with metadata."""
    regime: MarketRegime = MarketRegime.NO_SIGNAL
    macro_bias: MacroBias = MacroBias.NEUTRAL
    confidence: float = Field(default=0.0, ge=0, le=1.0)
    is_manual_override: bool = False
    override_expiration: Optional[datetime] = None
    active_events: list[MacroEvent] = Field(default_factory=list)
    event_lock_active: bool = False
    event_lock_expiration: Optional[datetime] = None
    volatility_level: float = Field(default=1.0, ge=0)
    classified_at: datetime = Field(default_factory=datetime.utcnow)
    classification_reason: str = ""


# ── Regime Update Request ─────────────────────────────────────

class RegimeUpdateRequest(BaseModel):
    """Manual regime override request from trader."""
    regime: Optional[MarketRegime] = None
    macro_bias: Optional[MacroBias] = None
    override_expiration_hours: Optional[float] = Field(default=24.0, ge=0)
    active_events: Optional[list[MacroEvent]] = None
    force_event_lock: Optional[bool] = None
    volatility_override: Optional[float] = Field(default=None, ge=0)


# ── Regime Classification Input ───────────────────────────────

class RegimeClassificationInput(BaseModel):
    """Input data for rule-based regime classification."""
    current_atr: float = Field(ge=0)
    atr_percentile: float = Field(ge=0, le=100)
    ma_fast: float = Field(gt=0)
    ma_slow: float = Field(gt=0)
    price: float = Field(gt=0)
    spread_bp: Optional[float] = None
    donchian_upper: float = Field(gt=0)
    donchian_lower: float = Field(gt=0)
    dcw: float = Field(ge=0)
    volume: int = Field(ge=0, default=0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
