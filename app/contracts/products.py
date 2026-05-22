"""Product and contract configuration models."""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TimeframeEnum(str, Enum):
    M1 = "1M"
    M5 = "5M"
    M15 = "15M"
    H1 = "1H"
    H4 = "4H"
    D1 = "1D"


class ProductConfig(BaseModel):
    """Validated product configuration from YAML."""
    product_key: str
    product_code: str
    display_name: str
    quote_format: str = "price"
    supported_timeframes: list[str] = Field(default_factory=list)
    outright_tick_size: float
    outright_tick_value: float
    spread_tick_size_bp: float
    spread_tick_value: float
    contracts: list[str] = Field(default_factory=list)
    spreads: list[str] = Field(default_factory=list)


class ProductSummary(BaseModel):
    """Summary view of a product for API responses."""
    product_key: str
    product_code: str
    display_name: str
    num_contracts: int
    num_spreads: int
    supported_timeframes: list[str]
