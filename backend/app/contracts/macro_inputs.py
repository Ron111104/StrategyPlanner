"""Macro input contract models for ZQ Strategy Planning Platform.

Defines regime state, macro bias, macro events, and regime update
request models used across the strategy evaluation pipeline.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator


class MarketRegime(StrEnum):
    """Market regime classification."""

    TREND = "trend"
    RANGE = "range"
    VOLATILITY = "volatility"
    EVENT = "event"


class MacroBias(StrEnum):
    """Directional macro bias for Fed policy expectations."""

    HAWKISH = "hawkish"
    DOVISH = "dovish"
    NEUTRAL = "neutral"


class MacroEvent(BaseModel):
    """A scheduled or active macroeconomic event that may impact Fed Funds pricing."""

    model_config = {"frozen": True}

    event_name: Annotated[str, Field(min_length=1, description="Event name e.g. 'FOMC Decision'")]
    event_time: datetime
    impact: Literal["high", "medium", "low"]
    description: Annotated[str, Field(default="", description="Optional event description")]


class RegimeState(BaseModel):
    """Current market regime state including macro context.

    Tracks the active regime classification, macro bias, confidence level,
    data source, expiration, and any active macro events.
    """

    current_regime: MarketRegime
    macro_bias: MacroBias
    confidence: Annotated[float, Field(ge=0.0, le=1.0, description="Confidence level 0-1")]
    source: Literal["manual", "computed"] = "computed"
    updated_at: datetime
    expires_at: datetime | None = None
    active_events: list[MacroEvent] = Field(default_factory=list)
    volatility_override: bool = False

    @field_validator("confidence")
    @classmethod
    def validate_confidence_range(cls, v: float) -> float:
        """Ensure confidence is clamped to [0.0, 1.0]."""
        if v < 0.0:
            return 0.0
        if v > 1.0:
            return 1.0
        return v


class RegimeUpdateRequest(BaseModel):
    """Request to update the current regime state.

    All fields are optional — only provided fields will be updated.
    """

    regime: MarketRegime | None = None
    bias: MacroBias | None = None
    events: list[MacroEvent] | None = None
    manual_override: bool = False
