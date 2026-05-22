"""Indicator computation result models."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class IndicatorResult(BaseModel):
    """Result from a single indicator computation."""
    name: str
    symbol: str
    timeframe: str
    values: list[float] = Field(default_factory=list)
    timestamps: list[datetime] = Field(default_factory=list)
    params: dict[str, float] = Field(default_factory=dict)
    upper_band: Optional[list[float]] = None
    lower_band: Optional[list[float]] = None
    middle_band: Optional[list[float]] = None
    signal_line: Optional[list[float]] = None
    histogram: Optional[list[float]] = None


class IndicatorSet(BaseModel):
    """Collection of indicator results for a symbol/timeframe."""
    symbol: str
    timeframe: str

    # Trend
    sma: dict[int, IndicatorResult] = Field(default_factory=dict)
    ema: dict[int, IndicatorResult] = Field(default_factory=dict)
    hma: dict[int, IndicatorResult] = Field(default_factory=dict)
    kama: dict[int, IndicatorResult] = Field(default_factory=dict)
    vwap: Optional[IndicatorResult] = None
    anchored_vwap: Optional[IndicatorResult] = None

    # Volatility
    atr: Optional[IndicatorResult] = None
    natr: Optional[IndicatorResult] = None
    historical_vol: Optional[IndicatorResult] = None
    realized_vol: Optional[IndicatorResult] = None
    bollinger_width: Optional[IndicatorResult] = None
    dcw: Optional[IndicatorResult] = None
    keltner: Optional[IndicatorResult] = None

    # Momentum
    rsi: Optional[IndicatorResult] = None
    stoch_rsi: Optional[IndicatorResult] = None
    macd: Optional[IndicatorResult] = None
    roc: Optional[IndicatorResult] = None
    momentum: Optional[IndicatorResult] = None
    ppo: Optional[IndicatorResult] = None

    # Structure
    donchian: Optional[IndicatorResult] = None
    bollinger: Optional[IndicatorResult] = None
    range_compression: Optional[IndicatorResult] = None
    expansion_detection: Optional[IndicatorResult] = None
    session_range: Optional[IndicatorResult] = None

    # Spread
    spread_zscore: Optional[IndicatorResult] = None
    spread_mean_dev: Optional[IndicatorResult] = None
    spread_velocity: Optional[IndicatorResult] = None
    spread_acceleration: Optional[IndicatorResult] = None
    curve_slope: Optional[IndicatorResult] = None
    curve_momentum: Optional[IndicatorResult] = None
    spread_atr: Optional[IndicatorResult] = None
    spread_dcw: Optional[IndicatorResult] = None

    # Liquidity
    relative_volume: Optional[IndicatorResult] = None
    volume_delta: Optional[IndicatorResult] = None
    bid_ask_width: Optional[IndicatorResult] = None
