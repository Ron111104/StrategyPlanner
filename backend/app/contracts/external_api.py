"""External API contract models for ZQ Strategy Planning Platform.

Defines Pydantic v2 models for raw external market data API responses
and internal fetch request/response wrappers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.contracts.market_data import OHLCVBar, Timeframe


class ExternalOHLCVResponse(BaseModel):
    """Raw OHLCV response from an external market data API.

    Handles varied field naming conventions from external providers
    and normalizes them into a consistent internal format.
    """

    timestamp: int | float | str = Field(description="Unix timestamp or ISO string")
    open: float | str = Field(description="Open price (may be string from some APIs)")
    high: float | str = Field(description="High price")
    low: float | str = Field(description="Low price")
    close: float | str = Field(description="Close price")
    volume: int | float | str = Field(default=0, description="Volume (may be string or float)")

    @field_validator("open", "high", "low", "close", mode="before")
    @classmethod
    def coerce_price_to_float(cls, v: float | str) -> float:
        """Coerce string prices to float."""
        return float(v)

    @field_validator("volume", mode="before")
    @classmethod
    def coerce_volume_to_int(cls, v: int | float | str) -> int:
        """Coerce volume to integer."""
        return int(float(v))

    @field_validator("timestamp", mode="before")
    @classmethod
    def coerce_timestamp(cls, v: int | float | str) -> int | float | str:
        """Pass through — parsing is done at the adapter layer."""
        return v


class ExternalQuoteResponse(BaseModel):
    """Raw quote data from an external market data API."""

    symbol: Annotated[str, Field(min_length=1, description="Instrument symbol")]
    bid: Annotated[float, Field(ge=0, description="Current bid price")]
    ask: Annotated[float, Field(ge=0, description="Current ask price")]
    last: Annotated[float, Field(ge=0, description="Last traded price")]
    volume: Annotated[int, Field(ge=0, description="Session volume")]
    timestamp: datetime
    change: float = Field(default=0.0, description="Price change from previous close")
    change_pct: float = Field(default=0.0, description="Percentage change from previous close")

    @field_validator("ask")
    @classmethod
    def ask_gte_bid(cls, v: float, info) -> float:  # type: ignore[no-untyped-def]
        """Validate that ask >= bid when both are positive."""
        bid = info.data.get("bid", 0.0)
        if v > 0 and bid > 0 and v < bid:
            raise ValueError(f"ask ({v}) must be >= bid ({bid})")
        return v


class MarketDataFetchRequest(BaseModel):
    """Internal request to fetch market data from an external source."""

    product: Annotated[str, Field(min_length=1, description="Product symbol to fetch")]
    timeframe: Timeframe
    limit: Annotated[int, Field(gt=0, le=10000, description="Maximum number of bars to fetch")] = 500
    start_time: datetime | None = None
    end_time: datetime | None = None

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v: datetime | None, info) -> datetime | None:  # type: ignore[no-untyped-def]
        """Validate end_time is after start_time if both are provided."""
        start = info.data.get("start_time")
        if v is not None and start is not None and v <= start:
            raise ValueError(f"end_time ({v}) must be after start_time ({start})")
        return v


class MarketDataFetchResponse(BaseModel):
    """Internal response wrapping fetched market data bars."""

    product: Annotated[str, Field(min_length=1)]
    timeframe: Timeframe
    bars: list[OHLCVBar] = Field(default_factory=list)
    source: Annotated[str, Field(min_length=1, description="Data source identifier")]
    fetched_at: datetime
