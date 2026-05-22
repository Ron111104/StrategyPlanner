"""Tests for the Multi-Timeframe Engine."""
import pytest
from datetime import datetime, timedelta

from app.contracts.market_data import OHLCVBar, OHLCVSeries
from app.contracts.regime import RegimeType, MacroBias
from app.services.cache import CacheManager
from app.services.indicator_engine import IndicatorEngine
from app.services.mtf_engine import MTFEngine, MTFAnalysis, TIMEFRAME_ORDER


@pytest.fixture
def mtf_engine():
    return MTFEngine()


@pytest.fixture
def multi_tf_cache():
    """Populate cache with data across multiple timeframes."""
    cache = CacheManager()
    cache.clear_all()
    cache.set_regime(RegimeType.TREND, MacroBias.HAWKISH)
    engine = IndicatorEngine()

    for tf in ["1H", "4H", "1D"]:
        bars = []
        price = 95.500
        for i in range(100):
            move = 0.005 * (1 if i % 2 == 0 else -1)
            o = price
            c = price + move
            h = max(o, c) + 0.005
            low = min(o, c) - 0.005
            bars.append(OHLCVBar(
                timestamp=datetime(2026, 1, 1) + timedelta(hours=i),
                open=round(o, 4), high=round(h, 4),
                low=round(low, 4), close=round(c, 4),
                volume=float(500 + i),
            ))
            price = c
        series = OHLCVSeries(symbol="FFN26", timeframe=tf, bars=bars, product_key="fed_funds")
        cache.set_ohlcv("FFN26", tf, series)
        engine.compute_all(series)

    return cache


class TestMTFAnalysis:
    def test_analyze_returns_result(self, multi_tf_cache, mtf_engine):
        result = mtf_engine.analyze("FFN26", "1H")
        assert isinstance(result, MTFAnalysis)
        assert result.symbol == "FFN26"
        assert result.anchor_tf == "1H"

    def test_composite_score_range(self, multi_tf_cache, mtf_engine):
        result = mtf_engine.analyze("FFN26", "1H")
        assert -1.0 <= result.composite_score <= 1.0

    def test_trend_alignment_range(self, multi_tf_cache, mtf_engine):
        result = mtf_engine.analyze("FFN26", "1H")
        assert -1.0 <= result.trend_alignment <= 1.0

    def test_volatility_alignment_range(self, multi_tf_cache, mtf_engine):
        result = mtf_engine.analyze("FFN26", "1H")
        assert 0.0 <= result.volatility_alignment <= 1.0

    def test_structure_alignment_range(self, multi_tf_cache, mtf_engine):
        result = mtf_engine.analyze("FFN26", "1H")
        assert 0.0 <= result.structure_alignment <= 1.0

    def test_direction_bias_valid(self, multi_tf_cache, mtf_engine):
        result = mtf_engine.analyze("FFN26", "1H")
        assert result.direction_bias in ("bullish", "bearish", "neutral")

    def test_timeframe_scores_populated(self, multi_tf_cache, mtf_engine):
        result = mtf_engine.analyze("FFN26", "1H")
        assert len(result.timeframe_scores) > 0

    def test_to_dict(self, multi_tf_cache, mtf_engine):
        result = mtf_engine.analyze("FFN26", "1H")
        d = result.to_dict()
        assert "symbol" in d
        assert "composite_score" in d
        assert "direction_bias" in d


class TestMTFAdjustments:
    def test_spacing_adjustment_range(self, multi_tf_cache, mtf_engine):
        mtf = mtf_engine.analyze("FFN26", "1H")
        adj = mtf_engine.get_spacing_adjustment(mtf)
        assert 0.5 <= adj <= 2.0

    def test_confidence_adjustment_range(self, multi_tf_cache, mtf_engine):
        mtf = mtf_engine.analyze("FFN26", "1H")
        adj = mtf_engine.get_confidence_adjustment(mtf)
        assert -0.2 <= adj <= 0.2

    def test_size_adjustment_range(self, multi_tf_cache, mtf_engine):
        mtf = mtf_engine.analyze("FFN26", "1H")
        adj = mtf_engine.get_size_adjustment(mtf)
        assert 0.5 <= adj <= 1.5


class TestMTFNoData:
    def test_no_data_returns_neutral(self, mtf_engine):
        cache = CacheManager()
        cache.clear_all()
        result = mtf_engine.analyze("UNKNOWN", "1H")
        assert result.direction_bias == "neutral"
        assert result.composite_score == 0.0


class TestMTFTimeframeOrder:
    def test_order(self):
        assert TIMEFRAME_ORDER == ["1M", "5M", "15M", "1H", "4H", "1D"]

    def test_1d_last(self):
        assert TIMEFRAME_ORDER[-1] == "1D"
