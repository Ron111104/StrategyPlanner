"""Market data domain models."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class OHLCVBar(BaseModel):
    """Single OHLCV bar."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class OHLCVSeries(BaseModel):
    """Time series of OHLCV bars for a single instrument."""
    symbol: str
    timeframe: str
    bars: list[OHLCVBar] = Field(default_factory=list)
    product_key: str = ""

    @property
    def length(self) -> int:
        return len(self.bars)

    @property
    def is_empty(self) -> bool:
        return len(self.bars) == 0

    @property
    def latest(self) -> Optional[OHLCVBar]:
        return self.bars[-1] if self.bars else None

    def closes(self) -> list[float]:
        return [b.close for b in self.bars]

    def highs(self) -> list[float]:
        return [b.high for b in self.bars]

    def lows(self) -> list[float]:
        return [b.low for b in self.bars]

    def opens(self) -> list[float]:
        return [b.open for b in self.bars]

    def volumes(self) -> list[float]:
        return [b.volume for b in self.bars]

    def timestamps(self) -> list[datetime]:
        return [b.timestamp for b in self.bars]


class MarketSnapshot(BaseModel):
    """Current market snapshot for a single instrument."""
    symbol: str
    product_key: str
    last_price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    change: float = 0.0
    change_pct: float = 0.0


class SpreadQuote(BaseModel):
    """Spread quote in basis points."""
    spread_symbol: str
    front_leg: str
    back_leg: str
    front_price: float
    back_price: float
    spread_bp: float
    product_key: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @staticmethod
    def compute_spread_bp(front_price: float, back_price: float) -> float:
        """Compute spread in basis points: (front - back) * 100."""
        return round((front_price - back_price) * 100, 2)
