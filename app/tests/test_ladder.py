"""Tests for the Adaptive Strategy Ladder Engine."""
import pytest
from datetime import datetime, timedelta

from app.contracts.market_data import OHLCVBar, OHLCVSeries
from app.contracts.ladder import LadderRequest, AdaptiveLadder, AdaptiveLadderLevel
from app.contracts.regime import RegimeType, MacroBias
from app.services.cache import CacheManager
from app.services.indicator_engine import IndicatorEngine
from app.services.ladder_engine import (
    LadderEngine,
    REGIME_SPACING,
    LOT_PROFILES,
    TIMEFRAME_MULT,
)
from app.core.exceptions import InsufficientDataError


@pytest.fixture
def ladder_engine():
    return LadderEngine()


@pytest.fixture
def seeded_cache(sample_series):
    """Populate cache with OHLCV + indicators so ladder engine can read them."""
    cache = CacheManager()
    cache.clear_all()
    cache.set_ohlcv("FFN26", "1H", sample_series)
    cache.set_regime(RegimeType.TREND, MacroBias.HAWKISH)
    engine = IndicatorEngine()
    engine.compute_all(sample_series)
    return cache


@pytest.fixture
def spread_series():
    bars = []
    price = -10.0
    for i in range(100):
        move = 0.5 * (1 if i % 3 == 0 else -1)
        o = price
        c = price + move
        h = max(o, c) + 0.5
        low = min(o, c) - 0.5
        bars.append(OHLCVBar(
            timestamp=datetime(2026, 1, 1) + timedelta(hours=i),
            open=o, high=h, low=low, close=c, volume=float(100 + i),
        ))
        price = c
    return OHLCVSeries(symbol="FFN26-FFQ26", timeframe="1H", bars=bars, product_key="fed_funds")


@pytest.fixture
def seeded_spread_cache(spread_series):
    cache = CacheManager()
    cache.clear_all()
    cache.set_ohlcv("FFN26-FFQ26", "1H", spread_series)
    cache.set_regime(RegimeType.TREND, MacroBias.DOVISH)
    engine = IndicatorEngine()
    engine.compute_all(spread_series)
    return cache


class TestLadderEngineBasic:
    def test_generate_outright_ladder(self, seeded_cache, ladder_engine):
        req = LadderRequest(
            product_key="fed_funds",
            symbol="FFN26",
            timeframe="1H",
            strategy="trend_fed_repricing",
        )
        ladder = ladder_engine.generate(req)
        assert isinstance(ladder, AdaptiveLadder)
        assert ladder.strategy == "trend_fed_repricing"
        assert ladder.symbol == "FFN26"
        assert ladder.instrument_type == "outright"
        assert ladder.total_lots > 0
        assert len(ladder.levels) > 0
        assert ladder.stop != 0.0
        assert ladder.target_1 != 0.0
        assert ladder.risk_reward > 0

    def test_generate_spread_ladder(self, seeded_spread_cache, ladder_engine):
        req = LadderRequest(
            product_key="fed_funds",
            symbol="FFN26-FFQ26",
            timeframe="1H",
            strategy="curve_steepener",
        )
        ladder = ladder_engine.generate(req)
        assert ladder.instrument_type == "spread"
        assert ladder.direction == "steepener"
        assert ladder.total_lots > 0
        assert ladder.entry_reference_bp is not None

    def test_event_regime_single_level(self, seeded_cache, ladder_engine):
        cache = CacheManager()
        cache.set_regime(RegimeType.EVENT, MacroBias.NEUTRAL)
        req = LadderRequest(
            product_key="fed_funds",
            symbol="FFN26",
            timeframe="1H",
            strategy="event_momentum",
        )
        ladder = ladder_engine.generate(req)
        assert len(ladder.levels) == 1

    def test_custom_max_levels(self, seeded_cache, ladder_engine):
        req = LadderRequest(
            product_key="fed_funds",
            symbol="FFN26",
            timeframe="1H",
            strategy="trend_fed_repricing",
            max_levels=3,
        )
        ladder = ladder_engine.generate(req)
        assert len(ladder.levels) <= 3

    def test_custom_direction(self, seeded_cache, ladder_engine):
        req = LadderRequest(
            product_key="fed_funds",
            symbol="FFN26",
            timeframe="1H",
            strategy="trend_fed_repricing",
            direction="short",
        )
        ladder = ladder_engine.generate(req)
        assert ladder.direction == "short"

    def test_no_data_raises(self, ladder_engine):
        cache = CacheManager()
        cache.clear_all()
        req = LadderRequest(
            product_key="fed_funds",
            symbol="UNKNOWN",
            timeframe="1H",
            strategy="trend_fed_repricing",
        )
        with pytest.raises(InsufficientDataError):
            ladder_engine.generate(req)


class TestLadderLevels:
    def test_levels_sorted_by_level_num(self, seeded_cache, ladder_engine):
        req = LadderRequest(
            product_key="fed_funds", symbol="FFN26",
            timeframe="1H", strategy="trend_fed_repricing",
        )
        ladder = ladder_engine.generate(req)
        for i in range(len(ladder.levels)):
            assert ladder.levels[i].level == i + 1

    def test_cumulative_lots_increasing(self, seeded_cache, ladder_engine):
        req = LadderRequest(
            product_key="fed_funds", symbol="FFN26",
            timeframe="1H", strategy="trend_fed_repricing",
        )
        ladder = ladder_engine.generate(req)
        for i in range(1, len(ladder.levels)):
            assert ladder.levels[i].cumulative_lots >= ladder.levels[i - 1].cumulative_lots

    def test_total_lots_matches_sum(self, seeded_cache, ladder_engine):
        req = LadderRequest(
            product_key="fed_funds", symbol="FFN26",
            timeframe="1H", strategy="trend_fed_repricing",
        )
        ladder = ladder_engine.generate(req)
        assert ladder.total_lots == sum(lv.lots for lv in ladder.levels)

    def test_avg_entry_between_levels(self, seeded_cache, ladder_engine):
        req = LadderRequest(
            product_key="fed_funds", symbol="FFN26",
            timeframe="1H", strategy="trend_fed_repricing",
        )
        ladder = ladder_engine.generate(req)
        prices = [lv.entry_price for lv in ladder.levels]
        assert min(prices) <= ladder.avg_entry <= max(prices)


class TestLadderSpacing:
    def test_trend_uses_atr(self):
        cfg = REGIME_SPACING["trend"]
        assert cfg["source"] == "ATR"
        assert cfg["atr_mult"] == 0.5

    def test_range_uses_dcw(self):
        cfg = REGIME_SPACING["range"]
        assert cfg["source"] == "DCW"
        assert cfg["dcw_mult"] == 0.25

    def test_volatility_wider_spacing(self):
        cfg = REGIME_SPACING["volatility"]
        assert cfg["atr_mult"] == 1.2

    def test_event_no_spacing(self):
        cfg = REGIME_SPACING["event"]
        assert cfg["source"] == "NONE"

    def test_timeframe_multipliers(self):
        assert TIMEFRAME_MULT["1M"] < TIMEFRAME_MULT["1H"]
        assert TIMEFRAME_MULT["1H"] < TIMEFRAME_MULT["1D"]


class TestLotProfiles:
    def test_pyramid_profile(self):
        p = LOT_PROFILES["pyramid"]
        assert len(p) == 5
        assert p[0] < p[-1]

    def test_equal_profile(self):
        p = LOT_PROFILES["equal"]
        assert all(v == p[0] for v in p)

    def test_front_loaded_profile(self):
        p = LOT_PROFILES["front_loaded"]
        assert p[0] > p[-1]


class TestLadderRiskReward:
    def test_rr_positive(self, seeded_cache, ladder_engine):
        req = LadderRequest(
            product_key="fed_funds", symbol="FFN26",
            timeframe="1H", strategy="trend_fed_repricing",
        )
        ladder = ladder_engine.generate(req)
        assert ladder.risk_reward > 0

    def test_total_risk_positive(self, seeded_cache, ladder_engine):
        req = LadderRequest(
            product_key="fed_funds", symbol="FFN26",
            timeframe="1H", strategy="trend_fed_repricing",
        )
        ladder = ladder_engine.generate(req)
        assert ladder.total_risk_usd > 0

    def test_stop_on_correct_side(self, seeded_cache, ladder_engine):
        # Long → stop below avg entry
        req = LadderRequest(
            product_key="fed_funds", symbol="FFN26",
            timeframe="1H", strategy="trend_fed_repricing",
            direction="long",
        )
        ladder = ladder_engine.generate(req)
        assert ladder.stop < ladder.avg_entry

        # Short → stop above avg entry
        req2 = LadderRequest(
            product_key="fed_funds", symbol="FFN26",
            timeframe="1H", strategy="trend_fed_repricing",
            direction="short",
        )
        ladder2 = ladder_engine.generate(req2)
        assert ladder2.stop > ladder2.avg_entry

    def test_target_on_correct_side(self, seeded_cache, ladder_engine):
        req = LadderRequest(
            product_key="fed_funds", symbol="FFN26",
            timeframe="1H", strategy="trend_fed_repricing",
            direction="long",
        )
        ladder = ladder_engine.generate(req)
        assert ladder.target_1 > ladder.avg_entry
