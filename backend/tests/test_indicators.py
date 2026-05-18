"""Tests for the Indicator Engine — ATR, SMA, EMA, Donchian, Bollinger, DCW."""
import pytest
from datetime import datetime, timezone, timedelta
from app.contracts.market_data import OHLCVBar, Timeframe, SpreadBar
from app.services.indicator_engine import IndicatorEngine

SETTINGS = {"indicators": {"atr_length": 14, "ma_fast": 5, "ma_slow": 10, "donchian_length": 10, "bollinger_length": 10, "bollinger_std": 2.0, "dcw_length": 10, "spread_sma_length": 10, "min_bars_required": 20}}

_BASE_DT = datetime(2026, 1, 1, tzinfo=timezone.utc)

def _make_bars(count: int, base_price: float = 96.5) -> list[OHLCVBar]:
    bars = []
    for i in range(count):
        p = base_price + (i * 0.005)
        bars.append(OHLCVBar(timestamp=_BASE_DT + timedelta(hours=i), open=p, high=p + 0.01, low=p - 0.005, close=p + 0.002, volume=100, timeframe=Timeframe.H1, product="FFN26"))
    return bars

def _make_spread_bars(count: int) -> list[SpreadBar]:
    bars = []
    for i in range(count):
        bp = 5.0 + i * 0.5
        bars.append(SpreadBar(timestamp=_BASE_DT + timedelta(hours=i), open_bp=bp, high_bp=bp + 1, low_bp=bp - 0.5, close_bp=bp + 0.2, volume=50, timeframe=Timeframe.H1, product="FFN26-FFQ26", front_contract="FFN26", back_contract="FFQ26"))
    return bars

class TestIndicatorEngine:
    def test_insufficient_bars(self):
        engine = IndicatorEngine(SETTINGS)
        bars = _make_bars(5)
        result = engine.compute(bars, "FFN26")
        assert not result.is_valid
        assert result.insufficient_bars

    def test_valid_computation(self):
        engine = IndicatorEngine(SETTINGS)
        bars = _make_bars(60)
        result = engine.compute(bars, "FFN26")
        assert result.is_valid
        assert result.current_atr > 0
        assert len(result.sma_fast) == 60
        assert len(result.donchian_upper) == 60
        assert result.current_donchian_upper > 0

    def test_atr_wilder_smoothing(self):
        engine = IndicatorEngine(SETTINGS)
        bars = _make_bars(60)
        result = engine.compute(bars, "FFN26")
        atr_vals = [v for v in result.atr if v > 0]
        assert len(atr_vals) > 0
        assert all(v >= 0 for v in result.atr)

    def test_bollinger_bands(self):
        engine = IndicatorEngine(SETTINGS)
        bars = _make_bars(60)
        result = engine.compute(bars, "FFN26")
        valid_upper = [v for v in result.bollinger_upper if v > 0]
        valid_lower = [v for v in result.bollinger_lower if v > 0]
        assert len(valid_upper) > 0
        for u, l in zip(valid_upper, valid_lower):
            assert u >= l

    def test_cache_hit(self):
        engine = IndicatorEngine(SETTINGS)
        bars = _make_bars(60)
        r1 = engine.compute(bars, "FFN26")
        r2 = engine.compute(bars, "FFN26")
        assert r1.current_atr == r2.current_atr

    def test_cache_invalidation(self):
        engine = IndicatorEngine(SETTINGS)
        bars = _make_bars(60)
        engine.compute(bars, "FFN26")
        engine.invalidate_cache("FFN26")
        assert "FFN26" not in str(engine._cache.keys()) or len(engine._cache) == 0

    def test_spread_indicators(self):
        engine = IndicatorEngine(SETTINGS)
        bars = _make_spread_bars(60)
        result = engine.compute_spread_indicators(bars, "FFN26-FFQ26")
        assert result.is_valid
        assert result.current_atr > 0
        assert len(result.spread_sma) > 0

    def test_donchian_channels(self):
        engine = IndicatorEngine(SETTINGS)
        bars = _make_bars(60)
        result = engine.compute(bars, "FFN26")
        valid_idx = [i for i, v in enumerate(result.donchian_upper) if v > 0]
        assert len(valid_idx) > 0
        for i in valid_idx:
            assert result.donchian_upper[i] >= result.donchian_lower[i]
