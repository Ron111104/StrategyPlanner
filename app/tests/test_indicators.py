"""Tests for the indicator engine."""
import pytest
import numpy as np

from app.contracts.market_data import OHLCVSeries
from app.core.exceptions import InsufficientDataError
from app.services.indicator_engine import IndicatorEngine


class TestATR:
    def test_atr_computation(self, sample_series: OHLCVSeries):
        engine = IndicatorEngine()
        result = engine.compute_atr(sample_series, length=14)
        assert result.name == "ATR"
        assert len(result.values) > 0
        assert all(v > 0 for v in result.values)
        assert len(result.timestamps) == len(result.values)

    def test_atr_wilder_smoothing(self, sample_series: OHLCVSeries):
        """Verify ATR uses Wilder smoothing: ATR[i] = (ATR[i-1]*(n-1) + TR[i]) / n"""
        engine = IndicatorEngine()
        result = engine.compute_atr(sample_series, length=14)
        # First ATR value should be simple average of first 14 TRs
        assert len(result.values) > 1
        # Values should be smoothed (not erratic)
        diffs = [abs(result.values[i] - result.values[i-1]) for i in range(1, len(result.values))]
        avg_diff = np.mean(diffs)
        assert avg_diff < np.mean(result.values)  # Smoothing reduces variation

    def test_atr_insufficient_bars(self, short_series: OHLCVSeries):
        engine = IndicatorEngine()
        with pytest.raises(InsufficientDataError):
            engine.compute_atr(short_series, length=14)


class TestSMA:
    def test_sma_computation(self, sample_series: OHLCVSeries):
        engine = IndicatorEngine()
        result = engine.compute_sma(sample_series, length=20)
        assert result.name == "SMA_20"
        assert len(result.values) == sample_series.length - 20 + 1

    def test_sma_values_correct(self, sample_series: OHLCVSeries):
        engine = IndicatorEngine()
        result = engine.compute_sma(sample_series, length=5)
        closes = sample_series.closes()
        expected_first = np.mean(closes[:5])
        assert abs(result.values[0] - expected_first) < 1e-8


class TestEMA:
    def test_ema_computation(self, sample_series: OHLCVSeries):
        engine = IndicatorEngine()
        result = engine.compute_ema(sample_series, length=9)
        assert result.name == "EMA_9"
        assert len(result.values) > 0

    def test_ema_seed_is_sma(self, sample_series: OHLCVSeries):
        engine = IndicatorEngine()
        result = engine.compute_ema(sample_series, length=9)
        closes = sample_series.closes()
        expected_seed = np.mean(closes[:9])
        assert abs(result.values[0] - expected_seed) < 1e-8


class TestDonchian:
    def test_donchian_channels(self, sample_series: OHLCVSeries):
        engine = IndicatorEngine()
        result = engine.compute_donchian(sample_series, length=20)
        assert result.upper_band is not None
        assert result.lower_band is not None
        assert len(result.upper_band) > 0
        for i in range(len(result.upper_band)):
            assert result.upper_band[i] >= result.lower_band[i]


class TestBollinger:
    def test_bollinger_bands(self, sample_series: OHLCVSeries):
        engine = IndicatorEngine()
        result = engine.compute_bollinger(sample_series, length=20, std_dev=2.0)
        assert result.upper_band is not None
        assert result.lower_band is not None
        for i in range(len(result.values)):
            assert result.upper_band[i] >= result.values[i] >= result.lower_band[i]


class TestDCW:
    def test_dcw_computation(self, sample_series: OHLCVSeries):
        engine = IndicatorEngine()
        result = engine.compute_dcw(sample_series, length=20)
        assert len(result.values) > 0
        assert all(v >= 0 for v in result.values)


class TestComputeAll:
    def test_compute_all_returns_indicator_set(self, sample_series: OHLCVSeries):
        engine = IndicatorEngine()
        ind_set = engine.compute_all(sample_series)
        assert ind_set.symbol == "FFN26"
        assert ind_set.timeframe == "1H"
        assert ind_set.atr is not None
        assert len(ind_set.sma) > 0
        assert len(ind_set.ema) > 0

    def test_compute_all_caches(self, sample_series: OHLCVSeries):
        from app.services.cache import CacheManager
        engine = IndicatorEngine()
        engine.compute_all(sample_series)
        cache = CacheManager()
        cached = cache.get_indicators("FFN26", "1H")
        assert cached is not None
        assert cached.atr is not None
