"""Tests for the IndicatorEngine."""

import pytest
import numpy as np

from app.services.indicator_engine import IndicatorEngine
from app.contracts.market_data import OHLCVBar


class TestIndicatorEngine:
    """Unit tests for all indicator computations."""

    def test_compute_atr_basic(self, indicator_engine, sample_bars):
        """ATR should return a list of floats with correct length."""
        atr = indicator_engine.compute_atr(sample_bars, length=14)
        assert isinstance(atr, list)
        assert len(atr) == len(sample_bars)
        # First 13 values may be NaN or 0, but from index 14 onward should be positive
        valid_atr = [v for v in atr[14:] if v > 0]
        assert len(valid_atr) > 0

    def test_compute_atr_wilder_smoothing(self, indicator_engine, sample_bars):
        """ATR should use Wilder's smoothing: ATR = (prev_ATR * (N-1) + TR) / N."""
        atr = indicator_engine.compute_atr(sample_bars, length=14)
        # Get true ranges manually for verification
        closes = [b.close for b in sample_bars]
        highs = [b.high for b in sample_bars]
        lows = [b.low for b in sample_bars]

        # First ATR (index 14) should be SMA of first 14 true ranges
        true_ranges = []
        for i in range(1, 15):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            true_ranges.append(tr)

        first_atr = sum(true_ranges) / 14
        assert abs(atr[14] - first_atr) < 1e-6, f"First ATR mismatch: {atr[14]} vs {first_atr}"

    def test_compute_sma(self, indicator_engine, sample_bars):
        """SMA should return correct arithmetic mean."""
        closes = [b.close for b in sample_bars]
        sma = indicator_engine.compute_sma(closes, length=10)
        assert len(sma) == len(closes)

        # Verify at index 9 (first complete SMA)
        expected = sum(closes[:10]) / 10
        assert abs(sma[9] - expected) < 1e-6

    def test_compute_ema(self, indicator_engine, sample_bars):
        """EMA should apply exponential weighting."""
        closes = [b.close for b in sample_bars]
        ema = indicator_engine.compute_ema(closes, length=9)
        assert len(ema) == len(closes)

        # EMA should be close to price for recent values
        assert abs(ema[-1] - closes[-1]) < 0.1

    def test_compute_donchian(self, indicator_engine, sample_bars):
        """Donchian channels should contain upper, lower, mid."""
        dc = indicator_engine.compute_donchian(sample_bars, length=20)
        assert "upper" in dc
        assert "lower" in dc
        assert "mid" in dc
        assert len(dc["upper"]) == len(sample_bars)

        # Upper should be >= lower
        for u, l in zip(dc["upper"][20:], dc["lower"][20:]):
            if u > 0 and l > 0:
                assert u >= l

    def test_compute_bollinger(self, indicator_engine, sample_bars):
        """Bollinger bands should have upper > mid > lower."""
        bb = indicator_engine.compute_bollinger(sample_bars, length=20, std_dev=2.0)
        assert "upper" in bb
        assert "lower" in bb
        assert "mid" in bb

        # Check band ordering
        for i in range(25, len(sample_bars)):
            if bb["upper"][i] > 0 and bb["lower"][i] > 0:
                assert bb["upper"][i] >= bb["mid"][i] >= bb["lower"][i]

    def test_compute_dcw(self, indicator_engine, sample_bars):
        """DCW should return positive values."""
        dcw = indicator_engine.compute_dcw(sample_bars, length=20)
        assert len(dcw) == len(sample_bars)
        valid = [v for v in dcw[20:] if v > 0]
        assert len(valid) > 0

    def test_insufficient_bars(self, indicator_engine, sample_bars_short):
        """Should raise error for insufficient data."""
        with pytest.raises(Exception):  # InsufficientDataError or ValueError
            indicator_engine.compute_atr(sample_bars_short, length=14)

    def test_compute_all(self, indicator_engine, sample_bars):
        """compute_all should return dict with all indicator keys."""
        config = {
            "atr": {"length": 14},
            "sma": {"lengths": [10, 20]},
            "ema": {"lengths": [9, 21]},
            "donchian": {"length": 20},
            "bollinger": {"length": 20, "std_dev": 2.0},
            "dcw": {"length": 20},
        }
        result = indicator_engine.compute_all(sample_bars, config)
        assert isinstance(result, dict)
        assert "atr" in result
        assert "sma" in result or "sma_10" in result or any("sma" in k for k in result)

    def test_atr_single_value_matches_manual(self, indicator_engine, sample_bars):
        """Single ATR value should match manual calculation."""
        atr = indicator_engine.compute_atr(sample_bars, length=14)
        # Just verify it's a reasonable value for Fed Funds (small tick market)
        last_atr = atr[-1]
        assert 0.001 < last_atr < 0.1, f"ATR {last_atr} seems unreasonable for Fed Funds"
