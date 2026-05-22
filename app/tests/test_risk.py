"""Tests for risk engine."""
import pytest

from app.services.risk_engine import RiskEngine


class TestTickHelpers:
    def test_price_to_ticks(self):
        engine = RiskEngine()
        assert engine.price_to_ticks(0.050, 0.005) == 10.0
        assert engine.price_to_ticks(0.025, 0.005) == 5.0

    def test_ticks_to_price(self):
        engine = RiskEngine()
        assert engine.ticks_to_price(10, 0.005) == 0.05

    def test_ticks_to_dollars(self):
        engine = RiskEngine()
        result = engine.ticks_to_dollars(10, 20.835)
        assert result == 208.35

    def test_spread_bp_to_ticks(self):
        engine = RiskEngine()
        assert engine.spread_bp_to_ticks(5.0, 0.5) == 10.0

    def test_zero_tick_size_raises(self):
        engine = RiskEngine()
        with pytest.raises(Exception):
            engine.price_to_ticks(0.050, 0)


class TestRiskProfile:
    def test_long_risk_profile(self, fed_funds_config):
        engine = RiskEngine()
        profile = engine.compute_risk_profile(
            symbol="FFN26",
            direction="long",
            entry_price=95.750,
            stop_price=95.700,
            target_price=95.900,
            product_key="fed_funds",
        )
        assert profile.risk_ticks == 10.0  # 0.050 / 0.005
        assert profile.reward_ticks == 30.0  # 0.150 / 0.005
        assert profile.risk_reward_ratio == 3.0
        assert profile.sizing is not None

    def test_short_risk_profile(self, fed_funds_config):
        engine = RiskEngine()
        profile = engine.compute_risk_profile(
            symbol="FFN26",
            direction="short",
            entry_price=95.900,
            stop_price=95.950,
            target_price=95.750,
            product_key="fed_funds",
        )
        assert profile.risk_ticks == 10.0
        assert profile.reward_ticks == 30.0
        assert profile.risk_reward_ratio == 3.0

    def test_spread_risk_profile(self, fed_funds_config):
        engine = RiskEngine()
        profile = engine.compute_risk_profile(
            symbol="FFN26-FFQ26",
            direction="long",
            entry_price=-15.0,
            stop_price=-20.0,
            target_price=-5.0,
            product_key="fed_funds",
            is_spread=True,
        )
        assert profile.tick_size == 0.5  # spread tick in bp
        assert profile.risk_ticks == 10.0  # 5.0 / 0.5
        assert profile.reward_ticks == 20.0


class TestLadderPlan:
    def test_entry_ladder_generated(self, fed_funds_config):
        engine = RiskEngine()
        profile = engine.compute_risk_profile(
            symbol="FFN26",
            direction="long",
            entry_price=95.750,
            stop_price=95.700,
            target_price=95.900,
            product_key="fed_funds",
        )
        assert profile.entry_ladder is not None
        assert len(profile.entry_ladder.levels) > 0
        assert profile.entry_ladder.total_lots > 0

    def test_target_ladder_generated(self, fed_funds_config):
        engine = RiskEngine()
        profile = engine.compute_risk_profile(
            symbol="FFN26",
            direction="long",
            entry_price=95.750,
            stop_price=95.700,
            target_price=95.900,
            product_key="fed_funds",
        )
        assert profile.target_ladder is not None
        assert len(profile.target_ladder.levels) > 0


class TestTradeAssessment:
    def test_assessment_with_warnings(self, sample_series, fed_funds_config):
        from app.services.cache import CacheManager
        from app.services.indicator_engine import IndicatorEngine

        cache = CacheManager()
        cache.set_ohlcv("FFN26", "1H", sample_series)
        ind_engine = IndicatorEngine()
        ind_engine.compute_all(sample_series)

        engine = RiskEngine()
        profile = engine.compute_risk_profile(
            symbol="FFN26",
            direction="long",
            entry_price=95.750,
            stop_price=95.700,
            target_price=95.900,
            product_key="fed_funds",
        )
        assessment = engine.assess_trade(profile, "FFN26", "1H")
        assert assessment.regime is not None
        assert assessment.macro_bias is not None
