"""Market data contract models for ZQ Strategy Planning Platform.

Defines Pydantic v2 models for price data, OHLCV bars, spread bars,
market snapshots, indicator config, and data ingestion payloads.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator


class Timeframe(StrEnum):
    """Supported bar timeframes."""

    M1 = "1M"
    M5 = "5M"
    M15 = "15M"
    H1 = "1H"
    H4 = "4H"
    D1 = "1D"


class PriceTick(BaseModel):
    """A single price tick from the market data feed."""

    model_config = {"frozen": True, "json_schema_extra": {"examples": [{"timestamp": "2025-07-15T14:30:00Z", "price": 95.755, "volume": 10, "product": "FFN25"}]}}

    timestamp: datetime
    price: Annotated[float, Field(gt=0, description="Tick price, must be positive")]
    volume: Annotated[int, Field(ge=0, description="Tick volume")]
    product: Annotated[str, Field(min_length=1, description="Product symbol e.g. FFN25")]


class OHLCVBar(BaseModel):
    """OHLCV bar for outright or spread products.

    Validates that high >= low and open/close are within [low, high].
    """

    model_config = {"frozen": True}

    timestamp: datetime
    open: Annotated[float, Field(gt=0, description="Bar open price")]
    high: Annotated[float, Field(gt=0, description="Bar high price")]
    low: Annotated[float, Field(gt=0, description="Bar low price")]
    close: Annotated[float, Field(gt=0, description="Bar close price")]
    volume: Annotated[int, Field(ge=0, description="Bar volume")]
    timeframe: Timeframe
    product: Annotated[str, Field(min_length=1, description="Product symbol")]

    @field_validator("high")
    @classmethod
    def high_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("high must be positive")
        return v

    @model_validator(mode="after")
    def validate_ohlc_consistency(self) -> OHLCVBar:
        """Ensure high >= low and open/close are within [low, high]."""
        if self.high < self.low:
            raise ValueError(
                f"high ({self.high}) must be >= low ({self.low})"
            )
        if not (self.low <= self.open <= self.high):
            raise ValueError(
                f"open ({self.open}) must be between low ({self.low}) and high ({self.high})"
            )
        if not (self.low <= self.close <= self.high):
            raise ValueError(
                f"close ({self.close}) must be between low ({self.low}) and high ({self.high})"
            )
        return self


class SpreadBar(BaseModel):
    """A spread bar computed from front and back contract prices.

    spread_bp is automatically computed as (front_price - back_price) * 100
    if not explicitly provided.
    """

    model_config = {"frozen": True}

    timestamp: datetime
    spread_bp: Annotated[float, Field(description="Spread in basis points")]
    front_price: Annotated[float, Field(gt=0, description="Front contract price")]
    back_price: Annotated[float, Field(gt=0, description="Back contract price")]
    volume: Annotated[int, Field(ge=0, description="Combined volume")]
    timeframe: Timeframe
    product: Annotated[str, Field(min_length=1, description="Spread product symbol e.g. FFN25-FFQ25")]

    @model_validator(mode="before")
    @classmethod
    def compute_spread_bp(cls, data: dict) -> dict:  # type: ignore[override]
        """Auto-compute spread_bp from front/back prices if not provided."""
        if isinstance(data, dict):
            front = data.get("front_price")
            back = data.get("back_price")
            if front is not None and back is not None:
                computed = round((float(front) - float(back)) * 100, 4)
                if "spread_bp" not in data or data["spread_bp"] is None:
                    data["spread_bp"] = computed
        return data


class MarketSnapshot(BaseModel):
    """A point-in-time snapshot of the market for a product pair.

    If both front and back contracts are provided, spread_bp is computed
    automatically.
    """

    model_config = {"frozen": True}

    front_contract: OHLCVBar
    back_contract: OHLCVBar | None = None
    spread_bp: float | None = None
    timestamp: datetime

    @model_validator(mode="after")
    def compute_spread(self) -> MarketSnapshot:
        """Compute spread_bp from front/back contract close prices."""
        if self.back_contract is not None and self.spread_bp is None:
            computed = round(
                (self.front_contract.close - self.back_contract.close) * 100, 4
            )
            # Since frozen, we use object.__setattr__
            object.__setattr__(self, "spread_bp", computed)
        return self


class IndicatorConfig(BaseModel):
    """Configuration for a technical indicator."""

    model_config = {"frozen": True}

    name: Annotated[str, Field(min_length=1, description="Indicator name e.g. 'atr', 'sma'")]
    length: Annotated[int, Field(gt=0, description="Lookback period")]
    params: dict[str, float | int | str | bool] = Field(
        default_factory=dict,
        description="Additional indicator-specific parameters",
    )


class MarketDataIngest(BaseModel):
    """Payload for ingesting a batch of OHLCV bars for a product/timeframe."""

    product: Annotated[str, Field(min_length=1, description="Product symbol")]
    timeframe: Timeframe
    bars: list[OHLCVBar] = Field(
        ..., min_length=1, description="List of OHLCV bars, at least one required"
    )

    @field_validator("bars")
    @classmethod
    def bars_must_be_sorted(cls, v: list[OHLCVBar]) -> list[OHLCVBar]:
        """Ensure bars are sorted by timestamp ascending."""
        for i in range(1, len(v)):
            if v[i].timestamp <= v[i - 1].timestamp:
                raise ValueError(
                    f"Bars must be sorted by timestamp ascending. "
                    f"Bar at index {i} ({v[i].timestamp}) <= bar at index {i - 1} ({v[i - 1].timestamp})"
                )
        return v
