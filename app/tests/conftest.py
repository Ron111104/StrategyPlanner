"""Shared test fixtures."""
import pytest
from datetime import datetime, timedelta
import random

from app.contracts.market_data import OHLCVBar, OHLCVSeries
from app.contracts.regime import MacroBias, RegimeState, RegimeType
from app.services.cache import CacheManager


def generate_ohlcv_bars(
    count: int = 100,
    start_price: float = 95.500,
    tick_size: float = 0.005,
    start_time: datetime | None = None,
    interval_minutes: int = 60,
) -> list[OHLCVBar]:
    """Generate synthetic OHLCV bars for testing."""
    if start_time is None:
        start_time = datetime(2026, 1, 1, 0, 0, 0)

    bars: list[OHLCVBar] = []
    price = start_price

    for i in range(count):
        move = random.choice([-1, 0, 1]) * tick_size * random.randint(1, 5)
        o = price
        c = price + move
        h = max(o, c) + tick_size * random.randint(0, 3)
        low = min(o, c) - tick_size * random.randint(0, 3)
        vol = float(random.randint(100, 5000))

        bars.append(OHLCVBar(
            timestamp=start_time + timedelta(minutes=interval_minutes * i),
            open=round(o, 4),
            high=round(h, 4),
            low=round(low, 4),
            close=round(c, 4),
            volume=vol,
        ))
        price = c

    return bars


@pytest.fixture
def sample_bars() -> list[OHLCVBar]:
    random.seed(42)
    return generate_ohlcv_bars(count=100)


@pytest.fixture
def sample_series(sample_bars: list[OHLCVBar]) -> OHLCVSeries:
    return OHLCVSeries(
        symbol="FFN26",
        timeframe="1H",
        bars=sample_bars,
        product_key="fed_funds",
    )


@pytest.fixture
def short_series() -> OHLCVSeries:
    random.seed(99)
    bars = generate_ohlcv_bars(count=5)
    return OHLCVSeries(symbol="FFN26", timeframe="1H", bars=bars, product_key="fed_funds")


@pytest.fixture
def trend_regime() -> RegimeState:
    return RegimeState(regime=RegimeType.TREND, macro_bias=MacroBias.DOVISH)


@pytest.fixture
def range_regime() -> RegimeState:
    return RegimeState(regime=RegimeType.RANGE, macro_bias=MacroBias.NEUTRAL)


@pytest.fixture
def event_regime() -> RegimeState:
    return RegimeState(regime=RegimeType.EVENT, macro_bias=MacroBias.HAWKISH)


@pytest.fixture
def fed_funds_config() -> dict:
    return {
        "product_code": "ZQ",
        "display_name": "Fed Funds Futures",
        "quote_format": "price",
        "outright_tick_size": 0.005,
        "outright_tick_value": 20.835,
        "spread_tick_size_bp": 0.5,
        "spread_tick_value": 20.835,
        "contracts": ["FFN26", "FFQ26", "FFU26"],
        "spreads": ["FFN26-FFQ26", "FFQ26-FFU26"],
    }


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset singleton cache between tests."""
    cache = CacheManager()
    cache.clear_all()
    yield
    cache.clear_all()
