"""API request models."""
from typing import Optional

from pydantic import BaseModel, Field

from app.contracts.regime import MacroBias, RegimeType


class FetchMarketDataRequest(BaseModel):
    """Request to fetch market data from external API."""
    product_key: str
    symbols: list[str]
    timeframe: str = "1H"


class IngestMarketDataRequest(BaseModel):
    """Request to ingest and process market data."""
    product_key: str
    symbols: list[str]
    timeframe: str = "1H"
    compute_indicators: bool = True


class EvaluateStrategyRequest(BaseModel):
    """Request to evaluate strategies for given symbols."""
    product_key: str
    symbols: list[str]
    timeframe: str = "1H"
    strategies: Optional[list[str]] = None  # None = all enabled
    regime: Optional[RegimeType] = None
    macro_bias: Optional[MacroBias] = None


class UpdateRegimeRequest(BaseModel):
    """Request to update market regime."""
    regime: RegimeType
    macro_bias: MacroBias
    notes: str = ""


class UpdateAccountConfigRequest(BaseModel):
    """Request to update account-level configuration."""
    max_position_lots: Optional[int] = None
    max_risk_per_trade_usd: Optional[float] = None
    max_daily_risk_usd: Optional[float] = None
    default_slippage_ticks: Optional[int] = None
    default_commission_per_lot: Optional[float] = None
