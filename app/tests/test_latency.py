"""Latency and performance tests."""
import pytest
import time
import random
from datetime import datetime, timedelta

from app.contracts.market_data import OHLCVBar, OHLCVSeries
from app.services.indicator_engine import IndicatorEngine
from app.services.risk_engine import RiskEngine
from app.services.cache import CacheManager


def generate_large_series(count: int) -> OHLCVSeries:
    random.seed(123)
    price = 95.500
    bars = []
    for i in range(count):
        move = random.choice([-1, 0, 1]) * 0.005 * random.randint(1, 5)
        o = price
        c = price + move
        h = max(o, c) + 0.005 * random.randint(0, 3)
        low = min(o, c) - 0.005 * random.randint(0, 3)
        bars.append(OHLCVBar(
            timestamp=datetime(2025, 1, 1) + timedelta(hours=i),
            open=round(o, 4), high=round(h, 4), low=round(low, 4),
            close=round(c, 4), volume=float(random.randint(100, 5000)),
        ))
        price = c
    return OHLCVSeries(symbol="FFN26", timeframe="1H", bars=bars, product_key="fed_funds")


class TestIndicatorLatency:
    def test_atr_1000_bars_under_50ms(self):
        series = generate_large_series(1000)
        engine = IndicatorEngine()
        start = time.perf_counter()
        engine.compute_atr(series, 14)
        elapsed = (time.perf_counter() - start) * 1000
        assert elapsed < 50, f"ATR took {elapsed:.1f}ms, expected < 50ms"

    def test_all_indicators_1000_bars_under_200ms(self):
        series = generate_large_series(1000)
        engine = IndicatorEngine()
        start = time.perf_counter()
        engine.compute_all(series)
        elapsed = (time.perf_counter() - start) * 1000
        assert elapsed < 200, f"All indicators took {elapsed:.1f}ms, expected < 200ms"

    def test_sma_5000_bars_under_100ms(self):
        series = generate_large_series(5000)
        engine = IndicatorEngine()
        start = time.perf_counter()
        engine.compute_sma(series, 20)
        elapsed = (time.perf_counter() - start) * 1000
        assert elapsed < 100, f"SMA took {elapsed:.1f}ms, expected < 100ms"

    def test_bollinger_5000_bars_under_150ms(self):
        series = generate_large_series(5000)
        engine = IndicatorEngine()
        start = time.perf_counter()
        engine.compute_bollinger(series, 20, 2.0)
        elapsed = (time.perf_counter() - start) * 1000
        assert elapsed < 150, f"Bollinger took {elapsed:.1f}ms, expected < 150ms"


class TestRiskLatency:
    def test_risk_profile_under_5ms(self):
        engine = RiskEngine()
        start = time.perf_counter()
        for _ in range(100):
            engine.compute_risk_profile(
                symbol="FFN26", direction="long",
                entry_price=95.750, stop_price=95.700, target_price=95.900,
                product_key="fed_funds",
            )
        elapsed = (time.perf_counter() - start) * 1000
        per_call = elapsed / 100
        assert per_call < 5, f"Risk profile took {per_call:.2f}ms/call, expected < 5ms"


class TestCacheLatency:
    def test_cache_read_write_under_1ms(self):
        cache = CacheManager()
        series = generate_large_series(100)

        start = time.perf_counter()
        for i in range(1000):
            cache.set_ohlcv(f"SYM{i}", "1H", series)
        write_elapsed = (time.perf_counter() - start) * 1000
        per_write = write_elapsed / 1000

        start = time.perf_counter()
        for i in range(1000):
            cache.get_ohlcv(f"SYM{i}", "1H")
        read_elapsed = (time.perf_counter() - start) * 1000
        per_read = read_elapsed / 1000

        assert per_write < 1, f"Cache write: {per_write:.3f}ms/op"
        assert per_read < 1, f"Cache read: {per_read:.3f}ms/op"
