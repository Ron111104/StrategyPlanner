"""Tests for newly added indicators: HMA, KAMA, VWAP, RSI, MACD, etc."""
import pytest
from datetime import datetime, timedelta

from app.contracts.market_data import OHLCVBar, OHLCVSeries
from app.services.indicator_engine import IndicatorEngine
from app.core.exceptions import InsufficientDataError


@pytest.fixture
def engine():
    return IndicatorEngine()


@pytest.fixture
def series_100():
    bars = []
    price = 95.500
    for i in range(100):
        move = 0.005 * (1 if i % 3 != 0 else -1) * (i % 5 + 1)
        o = price
        c = round(price + move, 4)
        h = round(max(o, c) + 0.01, 4)
        low = round(min(o, c) - 0.01, 4)
        bars.append(OHLCVBar(
            timestamp=datetime(2026, 1, 1) + timedelta(hours=i),
            open=o, high=h, low=low, close=c,
            volume=float(500 + i * 10),
        ))
        price = c
    return OHLCVSeries(symbol="FFN26", timeframe="1H", bars=bars, product_key="fed_funds")


@pytest.fixture
def spread_series():
    bars = []
    price = -10.0
    for i in range(100):
        move = 0.5 * (1 if i % 2 == 0 else -1)
        o = price
        c = price + move
        h = max(o, c) + 0.5
        low = min(o, c) - 0.5
        bars.append(OHLCVBar(
            timestamp=datetime(2026, 1, 1) + timedelta(hours=i),
            open=o, high=h, low=low, close=c,
            volume=float(100 + i),
        ))
        price = c
    return OHLCVSeries(symbol="FFN26-FFQ26", timeframe="1H", bars=bars, product_key="fed_funds")


class TestHMA:
    def test_hma_basic(self, engine, series_100):
        result = engine.compute_hma(series_100, 9)
        assert result.name == "HMA_9"
        assert len(result.values) > 0

    def test_hma_insufficient(self, engine):
        bars = [OHLCVBar(timestamp=datetime(2026, 1, 1, i), open=95.5, high=95.6, low=95.4, close=95.5, volume=100) for i in range(5)]
        series = OHLCVSeries(symbol="X", timeframe="1H", bars=bars)
        with pytest.raises(InsufficientDataError):
            engine.compute_hma(series, 9)


class TestKAMA:
    def test_kama_basic(self, engine, series_100):
        result = engine.compute_kama(series_100, 10)
        assert result.name == "KAMA_10"
        assert len(result.values) > 0

    def test_kama_adaptive(self, engine, series_100):
        result = engine.compute_kama(series_100, 10)
        # KAMA should not be constant
        assert len(set(round(v, 6) for v in result.values)) > 1


class TestVWAP:
    def test_vwap_basic(self, engine, series_100):
        result = engine.compute_vwap(series_100)
        assert result.name == "VWAP"
        assert len(result.values) > 0

    def test_anchored_vwap(self, engine, series_100):
        result = engine.compute_anchored_vwap(series_100, anchor_idx=50)
        assert result.name == "AVWAP"
        assert len(result.values) > 0


class TestNATR:
    def test_natr_basic(self, engine, series_100):
        result = engine.compute_natr(series_100, 14)
        assert result.name == "NATR"
        assert all(v >= 0 for v in result.values)


class TestHistoricalVol:
    def test_hv_basic(self, engine, series_100):
        result = engine.compute_historical_vol(series_100, 20)
        assert result.name == "HV_20"
        assert len(result.values) > 0
        assert all(v >= 0 for v in result.values)


class TestRealizedVol:
    def test_rv_basic(self, engine, series_100):
        result = engine.compute_realized_vol(series_100, 20)
        assert result.name == "RV_20"
        assert len(result.values) > 0


class TestBollingerWidth:
    def test_bbw_basic(self, engine, series_100):
        result = engine.compute_bollinger_width(series_100, 20, 2.0)
        assert result.name == "BBW_20"
        assert all(v >= 0 for v in result.values)


class TestKeltner:
    def test_keltner_bands(self, engine, series_100):
        result = engine.compute_keltner(series_100, 20, 1.5)
        assert result.upper_band is not None
        assert result.lower_band is not None
        assert len(result.upper_band) == len(result.lower_band)
        for i in range(len(result.values)):
            assert result.upper_band[i] >= result.lower_band[i]


class TestRSI:
    def test_rsi_basic(self, engine, series_100):
        result = engine.compute_rsi(series_100, 14)
        assert result.name == "RSI_14"
        assert all(0 <= v <= 100 for v in result.values)

    def test_rsi_length(self, engine, series_100):
        result = engine.compute_rsi(series_100, 14)
        assert len(result.values) > 0


class TestStochRSI:
    def test_stoch_rsi_basic(self, engine, series_100):
        result = engine.compute_stoch_rsi(series_100, 14, 14, 3, 3)
        assert result.name == "StochRSI"
        assert len(result.values) > 0
        assert result.signal_line is not None


class TestMACD:
    def test_macd_basic(self, engine, series_100):
        result = engine.compute_macd(series_100, 12, 26, 9)
        assert result.name == "MACD"
        assert len(result.values) > 0
        assert result.signal_line is not None
        assert result.histogram is not None
        assert len(result.histogram) == len(result.values)


class TestROC:
    def test_roc_basic(self, engine, series_100):
        result = engine.compute_roc(series_100, 14)
        assert result.name == "ROC_14"
        assert len(result.values) > 0


class TestMomentum:
    def test_momentum_basic(self, engine, series_100):
        result = engine.compute_momentum(series_100, 14)
        assert result.name == "MOM_14"
        assert len(result.values) > 0


class TestPPO:
    def test_ppo_basic(self, engine, series_100):
        result = engine.compute_ppo(series_100, 12, 26, 9)
        assert result.name == "PPO"
        assert len(result.values) > 0


class TestRangeCompression:
    def test_rc_basic(self, engine, series_100):
        result = engine.compute_range_compression(series_100, 20)
        assert result.name == "RC_20"
        assert len(result.values) > 0


class TestExpansionDetection:
    def test_expansion_basic(self, engine, series_100):
        result = engine.compute_expansion_detection(series_100, 20)
        assert all(v in (0.0, 1.0) for v in result.values)


class TestSessionRange:
    def test_session_range(self, engine, series_100):
        result = engine.compute_session_range(series_100)
        assert result.name == "SessionRange"
        assert len(result.values) == 100
        assert all(v >= 0 for v in result.values)


class TestSpreadIndicators:
    def test_spread_zscore(self, engine, spread_series):
        result = engine.compute_spread_zscore(spread_series, 20)
        assert "SpreadZ" in result.name

    def test_spread_mean_dev(self, engine, spread_series):
        result = engine.compute_spread_mean_deviation(spread_series, 20)
        assert "SpreadMeanDev" in result.name

    def test_spread_velocity(self, engine, spread_series):
        result = engine.compute_spread_velocity(spread_series, 5)
        assert len(result.values) > 0

    def test_spread_acceleration(self, engine, spread_series):
        result = engine.compute_spread_acceleration(spread_series, 5)
        assert len(result.values) > 0

    def test_curve_slope(self, engine, spread_series):
        result = engine.compute_curve_slope(spread_series, 10)
        assert "CurveSlope" in result.name

    def test_curve_momentum(self, engine, spread_series):
        result = engine.compute_curve_momentum(spread_series, 10)
        assert "CurveMom" in result.name


class TestLiquidity:
    def test_relative_volume(self, engine, series_100):
        result = engine.compute_relative_volume(series_100, 20)
        assert result.name == "RelVol_20"
        assert all(v >= 0 for v in result.values)

    def test_volume_delta(self, engine, series_100):
        result = engine.compute_volume_delta(series_100)
        assert result.name == "VolDelta"
        assert len(result.values) == 100


class TestComputeAll:
    def test_compute_all_outright(self, engine, series_100):
        ind = engine.compute_all(series_100)
        assert ind.atr is not None
        assert ind.rsi is not None
        assert ind.macd is not None
        assert ind.vwap is not None
        assert ind.dcw is not None
        assert ind.bollinger is not None
        assert ind.donchian is not None
        assert ind.relative_volume is not None
        assert ind.volume_delta is not None
        # Spread indicators should be None for outright
        assert ind.spread_zscore is None

    def test_compute_all_spread(self, engine, spread_series):
        ind = engine.compute_all(spread_series)
        assert ind.atr is not None
        assert ind.spread_zscore is not None
        assert ind.spread_velocity is not None
        assert ind.curve_slope is not None
