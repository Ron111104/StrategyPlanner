"""API response models."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.contracts.market_data import OHLCVBar, MarketSnapshot, SpreadQuote
from app.contracts.regime import RegimeState
from app.contracts.signals import SignalCard, StrategySignal
from app.contracts.strategy import EntryExitPlan, StrategyEvalResult


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MarketDataResponse(BaseModel):
    """Response from market data fetch/ingest."""
    success: bool
    symbols_loaded: list[str] = Field(default_factory=list)
    bars_per_symbol: dict[str, int] = Field(default_factory=dict)
    snapshots: list[MarketSnapshot] = Field(default_factory=list)
    spread_quotes: list[SpreadQuote] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class StrategyEvalResponse(BaseModel):
    """Response from strategy evaluation."""
    success: bool
    results: list[StrategyEvalResult] = Field(default_factory=list)
    total_signals: int = 0
    errors: list[str] = Field(default_factory=list)


class SignalResponse(BaseModel):
    """Response with current signals."""
    cards: list[SignalCard] = Field(default_factory=list)
    regime: Optional[RegimeState] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RegimeResponse(BaseModel):
    """Response from regime update."""
    success: bool
    state: RegimeState


class AccountConfigResponse(BaseModel):
    """Response from account config update."""
    success: bool
    config: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
