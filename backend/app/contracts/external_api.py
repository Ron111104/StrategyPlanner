"""
External API contracts — schemas for external data sources.

These schemas represent the RAW external API responses.
They are ONLY used inside adapters and MUST NOT leak into engine internals.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── QH API OHLC Response ─────────────────────────────────────

class QHOHLCCandle(BaseModel):
    """Single candle from QH API response (external schema)."""
    t: datetime = Field(description="Timestamp")
    o: float = Field(description="Open")
    h: float = Field(description="High")
    l: float = Field(description="Low")
    c: float = Field(description="Close")
    v: int = Field(description="Volume", default=0)


class QHOHLCProductResponse(BaseModel):
    """Product-level OHLC response from QH API."""
    product: str
    interval: str
    candles: list[QHOHLCCandle] = Field(default_factory=list)


class QHOHLCResponse(BaseModel):
    """Top-level QH API OHLC response."""
    data: list[QHOHLCProductResponse] = Field(default_factory=list)
    status: str = "ok"
    message: Optional[str] = None


# ── Generic API Error ─────────────────────────────────────────

class ExternalAPIError(BaseModel):
    """Structured external API error."""
    source: str
    status_code: int
    message: str
    raw_response: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
