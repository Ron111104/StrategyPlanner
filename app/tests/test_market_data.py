"""Tests for market data ingestion and caching."""
import pytest
from datetime import datetime

from app.contracts.market_data import OHLCVBar, OHLCVSeries, MarketSnapshot
from app.services.cache import CacheManager


class TestOHLCVBar:
    def test_bar_creation(self):
        bar = OHLCVBar(
            timestamp=datetime(2026, 6, 1, 10, 0),
            open=95.750,
            high=95.800,
            low=95.700,
            close=95.780,
            volume=1500.0,
        )
        assert bar.open == 95.750
        assert bar.close == 95.780


class TestOHLCVSeries:
    def test_series_properties(self, sample_series: OHLCVSeries):
        assert sample_series.length == 100
        assert not sample_series.is_empty
        assert sample_series.latest is not None

    def test_series_accessors(self, sample_series: OHLCVSeries):
        closes = sample_series.closes()
        highs = sample_series.highs()
        lows = sample_series.lows()
        assert len(closes) == 100
        assert len(highs) == 100
        assert len(lows) == 100

    def test_empty_series(self):
        series = OHLCVSeries(symbol="FFN26", timeframe="1H", bars=[])
        assert series.is_empty
        assert series.length == 0
        assert series.latest is None


class TestCacheManager:
    def test_singleton(self):
        c1 = CacheManager()
        c2 = CacheManager()
        assert c1 is c2

    def test_ohlcv_cache(self, sample_series):
        cache = CacheManager()
        cache.set_ohlcv("FFN26", "1H", sample_series)
        retrieved = cache.get_ohlcv("FFN26", "1H")
        assert retrieved is not None
        assert retrieved.length == 100

    def test_snapshot_created_on_ohlcv_cache(self, sample_series):
        cache = CacheManager()
        cache.set_ohlcv("FFN26", "1H", sample_series)
        snap = cache.get_snapshot("FFN26")
        assert snap is not None
        assert snap.last_price == sample_series.latest.close

    def test_regime_cache(self):
        from app.contracts.regime import RegimeType, MacroBias
        cache = CacheManager()
        state = cache.set_regime(RegimeType.TREND, MacroBias.HAWKISH, "Test")
        assert state.regime.value == "trend"
        assert state.macro_bias.value == "hawkish"
        retrieved = cache.get_regime()
        assert retrieved.regime.value == "trend"

    def test_account_cache(self):
        cache = CacheManager()
        config = cache.get_account()
        assert "max_position_lots" in config
        updated = cache.update_account({"max_position_lots": 50})
        assert updated["max_position_lots"] == 50

    def test_clear_all(self, sample_series):
        cache = CacheManager()
        cache.set_ohlcv("FFN26", "1H", sample_series)
        cache.clear_all()
        assert cache.get_ohlcv("FFN26", "1H") is None

    def test_spread_cache(self):
        from app.contracts.market_data import SpreadQuote
        cache = CacheManager()
        quote = SpreadQuote(
            spread_symbol="FFN26-FFQ26",
            front_leg="FFN26",
            back_leg="FFQ26",
            front_price=95.750,
            back_price=95.700,
            spread_bp=5.0,
            product_key="fed_funds",
        )
        cache.set_spread("FFN26-FFQ26", quote)
        retrieved = cache.get_spread("FFN26-FFQ26")
        assert retrieved is not None
        assert retrieved.spread_bp == 5.0


class TestAdapterParsing:
    def test_timestamp_parsing(self):
        from app.adapters.qh_adapter import QHAdapter
        adapter = QHAdapter()

        # ISO format
        dt = adapter._parse_timestamp("2026-06-01T10:00:00")
        assert dt.year == 2026

        # Unix seconds
        dt = adapter._parse_timestamp(1780300800)
        assert isinstance(dt, datetime)

        # Unix milliseconds
        dt = adapter._parse_timestamp(1780300800000)
        assert isinstance(dt, datetime)

    def test_timeframe_mapping(self):
        from app.adapters.qh_adapter import QHAdapter, TIMEFRAME_MAP
        assert TIMEFRAME_MAP["1H"] == "1hour"
        assert TIMEFRAME_MAP["1D"] == "1day"
        assert TIMEFRAME_MAP["5M"] == "5min"
