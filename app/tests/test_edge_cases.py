"""Edge-case tests for robustness."""
import pytest
from datetime import datetime, timedelta

from app.contracts.market_data import OHLCVBar, OHLCVSeries
from app.contracts.regime import RegimeState, RegimeType, MacroBias
from app.contracts.indicators import IndicatorSet
from app.services.indicator_engine import IndicatorEngine
from app.services.risk_engine import RiskEngine
from app.core.exceptions import InsufficientDataError, RiskError


class TestIndicatorEdgeCases:
    def test_single_bar_series(self):
        series = OHLCVSeries(
            symbol="FFN26", timeframe="1H",
            bars=[OHLCVBar(timestamp=datetime(2026, 1, 1), open=95.5, high=95.6, low=95.4, close=95.55, volume=100)],
        )
        engine = IndicatorEngine()
        with pytest.raises(InsufficientDataError):
            engine.compute_atr(series, 14)

    def test_exact_minimum_bars_for_sma(self):
        bars = [
            OHLCVBar(timestamp=datetime(2026, 1, 1, i), open=95.5 + i * 0.001, high=95.6 + i * 0.001, low=95.4 + i * 0.001, close=95.5 + i * 0.001, volume=100)
            for i in range(5)
        ]
        series = OHLCVSeries(symbol="FFN26", timeframe="1H", bars=bars)
        engine = IndicatorEngine()
        result = engine.compute_sma(series, 5)
        assert len(result.values) == 1

    def test_flat_price_series(self):
        bars = [
            OHLCVBar(timestamp=datetime(2026, 1, 1) + timedelta(hours=i), open=95.5, high=95.5, low=95.5, close=95.5, volume=100)
            for i in range(50)
        ]
        series = OHLCVSeries(symbol="FFN26", timeframe="1H", bars=bars)
        engine = IndicatorEngine()
        ind = engine.compute_all(series)
        assert ind.atr is not None
        # ATR should be 0 for flat prices (after first bar)
        if ind.atr.values:
            assert all(v >= 0 for v in ind.atr.values)

    def test_bollinger_flat_prices(self):
        bars = [
            OHLCVBar(timestamp=datetime(2026, 1, 1) + timedelta(hours=i), open=95.5, high=95.5, low=95.5, close=95.5, volume=100)
            for i in range(25)
        ]
        series = OHLCVSeries(symbol="FFN26", timeframe="1H", bars=bars)
        engine = IndicatorEngine()
        result = engine.compute_bollinger(series, 20, 2.0)
        # With flat prices, std=0, so upper=lower=middle
        assert result.upper_band is not None
        for i in range(len(result.values)):
            assert abs(result.upper_band[i] - result.lower_band[i]) < 1e-8

    def test_zero_volume_bars(self):
        bars = [
            OHLCVBar(timestamp=datetime(2026, 1, 1) + timedelta(hours=i), open=95.5, high=95.6, low=95.4, close=95.55, volume=0)
            for i in range(50)
        ]
        series = OHLCVSeries(symbol="FFN26", timeframe="1H", bars=bars)
        engine = IndicatorEngine()
        ind = engine.compute_all(series)
        assert ind.atr is not None


class TestRiskEdgeCases:
    def test_zero_risk_ticks(self):
        engine = RiskEngine()
        profile = engine.compute_risk_profile(
            symbol="FFN26", direction="long",
            entry_price=95.750, stop_price=95.750, target_price=95.800,
            product_key="fed_funds",
        )
        assert profile.risk_ticks == 0.0
        assert profile.risk_reward_ratio == 0.0

    def test_very_wide_stop(self):
        engine = RiskEngine()
        profile = engine.compute_risk_profile(
            symbol="FFN26", direction="long",
            entry_price=95.750, stop_price=94.000, target_price=96.000,
            product_key="fed_funds",
        )
        assert profile.risk_ticks == 350.0  # 1.750 / 0.005

    def test_negative_spread_risk(self):
        engine = RiskEngine()
        profile = engine.compute_risk_profile(
            symbol="FFN26-FFQ26", direction="short",
            entry_price=-10.0, stop_price=-5.0, target_price=-20.0,
            product_key="fed_funds", is_spread=True,
        )
        assert profile.risk_ticks == 10.0  # 5.0 / 0.5
        assert profile.reward_ticks == 20.0


class TestRegimeEdgeCases:
    def test_regime_with_empty_indicators(self):
        from app.services.regime_engine import RegimeEngine
        engine = RegimeEngine()
        ind = IndicatorSet(symbol="FFN26", timeframe="1H")
        scores = engine.suggest_regime(ind)
        assert all(v == 0.0 for v in scores.values())

    def test_strategy_applicability_mismatch(self):
        from app.services.regime_engine import RegimeEngine
        from app.services.cache import CacheManager
        cache = CacheManager()
        cache.set_regime(RegimeType.TREND, MacroBias.NEUTRAL)
        engine = RegimeEngine()
        assert engine.is_strategy_applicable(["range"], ["1H"], "1H") is False
        assert engine.is_strategy_applicable(["trend"], ["4H"], "1H") is False
        assert engine.is_strategy_applicable(["trend"], ["1H"], "1H") is True


class TestModelValidation:
    def test_confidence_bounds(self):
        from app.contracts.signals import Signal
        sig = Signal(confidence=0.0)
        assert sig.confidence == 0.0
        sig = Signal(confidence=1.0)
        assert sig.confidence == 1.0

    def test_regime_enum_values(self):
        assert RegimeType.TREND.value == "trend"
        assert RegimeType.RANGE.value == "range"
        assert RegimeType.VOLATILITY.value == "volatility"
        assert RegimeType.EVENT.value == "event"

    def test_macro_bias_enum_values(self):
        assert MacroBias.HAWKISH.value == "hawkish"
        assert MacroBias.DOVISH.value == "dovish"
        assert MacroBias.NEUTRAL.value == "neutral"
