"""
Market data domain contracts — canonical internal schemas.

All external data MUST be normalized to these contracts before
entering the engine. External schemas NEVER leak past adapters.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ── Enums ─────────────────────────────────────────────────────

class Timeframe(str, Enum):
    """Supported OHLCV timeframes."""
    M1 = "1M"
    M5 = "5M"
    M15 = "15M"
    H1 = "1H"
    H4 = "4H"
    D1 = "1D"


class ContractType(str, Enum):
    """Contract instrument type."""
    OUTRIGHT = "outright"
    SPREAD = "spread"


# ── Price Tick ────────────────────────────────────────────────

class PriceTick(BaseModel):
    """Single price tick observation."""
    timestamp: datetime
    price: float = Field(gt=0, description="Price in price format (e.g., 96.500)")
    volume: int = Field(ge=0, default=0)
    product: str


# ── OHLCV Bar ────────────────────────────────────────────────

class OHLCVBar(BaseModel):
    """
    Single OHLCV bar in canonical internal format.

    Outright bars: prices in price format (e.g., 96.500).
    Tick size = 0.005, Tick value = $20.835.
    """
    timestamp: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: int = Field(ge=0, default=0)
    timeframe: Timeframe
    product: str

    @field_validator("high")
    @classmethod
    def high_gte_low(cls, v: float, info) -> float:
        low = info.data.get("low")
        if low is not None and v < low:
            raise ValueError(f"high ({v}) must be >= low ({low})")
        return v

    @field_validator("high")
    @classmethod
    def high_gte_open_close(cls, v: float, info) -> float:
        for field_name in ("open", "close"):
            val = info.data.get(field_name)
            if val is not None and v < val:
                raise ValueError(f"high ({v}) must be >= {field_name} ({val})")
        return v

    @field_validator("low")
    @classmethod
    def low_lte_open_close(cls, v: float, info) -> float:
        for field_name in ("open",):
            val = info.data.get(field_name)
            if val is not None and v > val:
                raise ValueError(f"low ({v}) must be <= {field_name} ({val})")
        return v


# ── Spread Bar ────────────────────────────────────────────────

class SpreadBar(BaseModel):
    """
    Spread bar stored internally in BASIS POINTS.

    spread_bp = (front_price - back_price) * 100
    Spread tick size = 0.5 bp, Tick value = $20.835.
    """
    timestamp: datetime
    open_bp: float = Field(description="Spread open in basis points")
    high_bp: float = Field(description="Spread high in basis points")
    low_bp: float = Field(description="Spread low in basis points")
    close_bp: float = Field(description="Spread close in basis points")
    volume: int = Field(ge=0, default=0)
    timeframe: Timeframe
    product: str
    front_contract: str
    back_contract: str


# ── Market Snapshot ───────────────────────────────────────────

class MarketSnapshot(BaseModel):
    """
    Combined snapshot of front + back contracts with computed spread.

    Automatically computes spread_bp from front and back prices.
    """
    timestamp: datetime
    front_contract: str
    back_contract: str
    front_price: float = Field(gt=0)
    back_price: float = Field(gt=0)
    spread_bp: float = Field(description="Computed: (front - back) * 100")
    front_volume: int = Field(ge=0, default=0)
    back_volume: int = Field(ge=0, default=0)
    timeframe: Timeframe

    @classmethod
    def from_prices(
        cls,
        timestamp: datetime,
        front_contract: str,
        back_contract: str,
        front_price: float,
        back_price: float,
        front_volume: int = 0,
        back_volume: int = 0,
        timeframe: Timeframe = Timeframe.H1,
    ) -> MarketSnapshot:
        """Factory: compute spread_bp from front/back prices."""
        spread_bp = round((front_price - back_price) * 100, 2)
        return cls(
            timestamp=timestamp,
            front_contract=front_contract,
            back_contract=back_contract,
            front_price=front_price,
            back_price=back_price,
            spread_bp=spread_bp,
            front_volume=front_volume,
            back_volume=back_volume,
            timeframe=timeframe,
        )


# ── Indicator Config ─────────────────────────────────────────

class IndicatorConfig(BaseModel):
    """Configuration for indicator computation."""
    atr_length: int = Field(default=14, ge=1)
    ma_fast: int = Field(default=10, ge=1)
    ma_slow: int = Field(default=50, ge=1)
    donchian_length: int = Field(default=20, ge=1)
    bollinger_length: int = Field(default=20, ge=1)
    bollinger_std: float = Field(default=2.0, gt=0)
    dcw_length: int = Field(default=20, ge=1)
    spread_sma_length: int = Field(default=20, ge=1)
    min_bars_required: int = Field(default=51, ge=1)


# ── Market Data Ingest Request ────────────────────────────────

class MarketDataIngest(BaseModel):
    """Request to ingest market data bars."""
    product: str = Field(min_length=1)
    timeframe: Timeframe = Timeframe.H1
    bars: list[OHLCVBar] = Field(min_length=1)


# ── Market Data Fetch Request ────────────────────────────────

class MarketDataFetchRequest(BaseModel):
    """Request to fetch market data from external API."""
    products: list[str] = Field(min_length=1)
    timeframe: Timeframe = Timeframe.H1
    bar_count: Optional[int] = Field(default=200, ge=1, le=1000)
