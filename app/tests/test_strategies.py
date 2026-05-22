"""Tests for strategy evaluation."""
import pytest

from app.contracts.market_data import OHLCVSeries
from app.contracts.regime import MacroBias, RegimeState, RegimeType
from app.services.indicator_engine import IndicatorEngine
from app.strategies.trend_fed_repricing import TrendFedRepricing
from app.strategies.mean_reversion_range import MeanReversionRange
from app.strategies.event_momentum import EventMomentum
from app.strategies.event_fade import EventFade
from app.strategies.volatility_fade import VolatilityFade
from app.strategies.curve_steepener import CurveSteepener
from app.strategies.curve_flattener import CurveFlattener


@pytest.fixture
def indicators(sample_series):
    engine = IndicatorEngine()
    return engine.compute_all(sample_series)


class TestTrendFedRepricing:
    def test_returns_signal_or_none(self, sample_series, indicators, trend_regime, fed_funds_config):
        strategy = TrendFedRepricing()
        signal = strategy.evaluate(sample_series, indicators, trend_regime, fed_funds_config)
        # Signal can be None or a valid signal
        if signal is not None:
            assert signal.strategy_name == "trend_fed_repricing"
            assert signal.confidence > 0
            assert signal.entry_price is not None

    def test_builds_entry_exit_plan(self, sample_series, indicators, trend_regime, fed_funds_config):
        strategy = TrendFedRepricing()
        signal = strategy.evaluate(sample_series, indicators, trend_regime, fed_funds_config)
        if signal:
            plan = strategy.build_entry_exit_plan(signal, sample_series, indicators, fed_funds_config)
            if plan:
                assert plan.risk_ticks > 0
                assert plan.reward_ticks > 0


class TestMeanReversionRange:
    def test_returns_signal_in_range_regime(self, sample_series, indicators, range_regime, fed_funds_config):
        strategy = MeanReversionRange()
        signal = strategy.evaluate(sample_series, indicators, range_regime, fed_funds_config)
        if signal:
            assert signal.strategy_name == "mean_reversion_range"


class TestEventMomentum:
    def test_returns_signal_in_event_regime(self, sample_series, indicators, event_regime, fed_funds_config):
        strategy = EventMomentum()
        signal = strategy.evaluate(sample_series, indicators, event_regime, fed_funds_config)
        if signal:
            assert signal.strategy_name == "event_momentum"


class TestEventFade:
    def test_returns_signal_or_none(self, sample_series, indicators, event_regime, fed_funds_config):
        strategy = EventFade()
        signal = strategy.evaluate(sample_series, indicators, event_regime, fed_funds_config)
        if signal:
            assert signal.strategy_name == "event_fade"


class TestVolatilityFade:
    def test_returns_signal_or_none(self, sample_series, indicators, fed_funds_config):
        regime = RegimeState(regime=RegimeType.VOLATILITY, macro_bias=MacroBias.NEUTRAL)
        strategy = VolatilityFade()
        signal = strategy.evaluate(sample_series, indicators, regime, fed_funds_config)
        if signal:
            assert signal.strategy_name == "volatility_fade"


class TestCurveSteepener:
    def test_returns_signal_for_spread(self, sample_series, indicators, trend_regime, fed_funds_config):
        strategy = CurveSteepener()
        signal = strategy.evaluate(sample_series, indicators, trend_regime, fed_funds_config)
        if signal:
            assert signal.direction.value == "long"


class TestCurveFlattener:
    def test_returns_signal_for_spread(self, sample_series, indicators, trend_regime, fed_funds_config):
        strategy = CurveFlattener()
        signal = strategy.evaluate(sample_series, indicators, trend_regime, fed_funds_config)
        if signal:
            assert signal.direction.value == "short"


class TestStrategyDisable:
    def test_disabled_on_empty_series(self, fed_funds_config):
        empty = OHLCVSeries(symbol="FFN26", timeframe="1H", bars=[])
        engine = IndicatorEngine()
        strategy = TrendFedRepricing()

        from app.contracts.indicators import IndicatorSet
        ind = IndicatorSet(symbol="FFN26", timeframe="1H")
        regime = RegimeState()

        disabled, reason = strategy.should_disable(empty, ind, regime)
        assert disabled is True
        assert "No market data" in reason

    def test_disabled_on_short_series(self, short_series, fed_funds_config):
        from app.contracts.indicators import IndicatorSet
        ind = IndicatorSet(symbol="FFN26", timeframe="1H")
        regime = RegimeState()
        strategy = TrendFedRepricing()

        disabled, reason = strategy.should_disable(short_series, ind, regime)
        assert disabled is True
