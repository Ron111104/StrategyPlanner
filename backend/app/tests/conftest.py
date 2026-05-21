"""
Pytest fixtures for ZQ Strategy Planner test suite.

Generates realistic Fed Funds Futures test data and provides
pre-configured service instances.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.contracts.execution_inputs import AccountConfig
from app.contracts.macro_inputs import MacroBias, MacroEvent, MarketRegime, RegimeState
from app.contracts.market_data import OHLCVBar, SpreadBar, Timeframe
from app.services.indicator_engine import IndicatorEngine
from app.services.regime_engine import RegimeEngine
from app.services.risk_engine import RiskEngine


def _generate_realistic_bars(
    count: int = 60,
    start_price: float = 95.800,
    product: str = "FFN25",
    timeframe: str = "1H",
) -> list[OHLCVBar]:
    """Generate realistic Fed Funds Futures OHLCV bars."""
    bars: list[OHLCVBar] = []
    base_time = datetime(2025, 6, 1, 8, 0, 0, tzinfo=timezone.utc)
    price = start_price
    random.seed(42)  # Reproducible

    for i in range(count):
        # Small random walk typical of Fed Funds
        change = random.gauss(0, 0.008)
        open_price = round(price, 3)

        high_add = abs(random.gauss(0.005, 0.003))
        low_sub = abs(random.gauss(0.005, 0.003))

        close_price = round(open_price + change, 3)
        high_price = round(max(open_price, close_price) + high_add, 3)
        low_price = round(min(open_price, close_price) - low_sub, 3)
        volume = random.randint(500, 5000)

        bars.append(
            OHLCVBar(
                timestamp=base_time + timedelta(hours=i),
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume,
                timeframe=Timeframe(timeframe),
                product=product,
            )
        )
        price = close_price

    return bars


@pytest.fixture
def sample_bars() -> list[OHLCVBar]:
    """60 realistic Fed Funds Futures OHLCV bars."""
    return _generate_realistic_bars(count=60)


@pytest.fixture
def sample_bars_short() -> list[OHLCVBar]:
    """10 bars — insufficient for signal generation."""
    return _generate_realistic_bars(count=10)


@pytest.fixture
def sample_spread_bars() -> list[SpreadBar]:
    """60 realistic spread bars in basis points."""
    bars: list[SpreadBar] = []
    base_time = datetime(2025, 6, 1, 8, 0, 0, tzinfo=timezone.utc)
    random.seed(42)
    front_price = 95.800
    back_price = 95.750

    for i in range(60):
        front_price += random.gauss(0, 0.005)
        back_price += random.gauss(0, 0.005)
        spread_bp = (front_price - back_price) * 100

        bars.append(
            SpreadBar(
                timestamp=base_time + timedelta(hours=i),
                spread_bp=round(spread_bp, 1),
                front_price=round(front_price, 3),
                back_price=round(back_price, 3),
                volume=random.randint(100, 2000),
                timeframe=Timeframe("1H"),
                product="FFN25-FFQ25",
            )
        )

    return bars


@pytest.fixture
def sample_account_config() -> AccountConfig:
    """Default account configuration for testing."""
    return AccountConfig(
        account_size_usd=100_000.0,
        risk_per_trade_usd=500.0,
        max_risk_per_trade_usd=2000.0,
        max_position_size=50,
        slippage_ticks=1,
        commission_per_side=2.50,
        event_risk_reduction=0.5,
    )


@pytest.fixture
def sample_regime_state() -> RegimeState:
    """Default regime state for testing."""
    return RegimeState(
        current_regime=MarketRegime.RANGE,
        macro_bias=MacroBias.NEUTRAL,
        confidence=0.75,
        source="computed",
        updated_at=datetime.now(timezone.utc),
        expires_at=None,
        active_events=[],
        volatility_override=False,
    )


@pytest.fixture
def sample_event_regime_state() -> RegimeState:
    """Event regime state for testing."""
    return RegimeState(
        current_regime=MarketRegime.EVENT,
        macro_bias=MacroBias.HAWKISH,
        confidence=0.9,
        source="computed",
        updated_at=datetime.now(timezone.utc),
        active_events=[
            MacroEvent(
                event_name="FOMC Decision",
                event_time=datetime.now(timezone.utc) + timedelta(hours=1),
                impact="high",
                description="Federal Reserve interest rate decision",
            )
        ],
        volatility_override=True,
    )


@pytest.fixture
def indicator_engine() -> IndicatorEngine:
    """Pre-configured indicator engine."""
    return IndicatorEngine(
        config={
            "atr": {"length": 14, "smoothing": "wilder"},
            "sma": {"lengths": [10, 20, 50]},
            "ema": {"lengths": [9, 21, 50]},
            "donchian": {"length": 20},
            "bollinger": {"length": 20, "std_dev": 2.0},
            "dcw": {"length": 20},
        }
    )


@pytest.fixture
def risk_engine() -> RiskEngine:
    """Pre-configured risk engine."""
    return RiskEngine(
        config={
            "default_risk_per_trade_usd": 500.0,
            "max_risk_per_trade_usd": 2000.0,
            "default_slippage_ticks": 1,
            "default_commission_per_side": 2.50,
            "event_risk_reduction": 0.5,
            "max_position_size": 50,
        }
    )


@pytest.fixture
def regime_engine() -> RegimeEngine:
    """Pre-configured regime engine."""
    return RegimeEngine(
        config={
            "trend_atr_threshold": 1.5,
            "volatility_atr_threshold": 2.0,
            "range_dcw_threshold": 0.3,
            "event_window_hours": 4,
            "regime_expiry_hours": 24,
        }
    )
