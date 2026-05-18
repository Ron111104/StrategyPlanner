"""Tests for Strategy Engine, Regime Engine, Spread Math, and Validation."""
import pytest
from datetime import datetime, timezone, timedelta
from app.contracts.market_data import OHLCVBar, Timeframe, ContractType
from app.contracts.macro_inputs import MarketRegime, MacroBias, RegimeUpdateRequest, RegimeClassificationInput
from app.services.indicator_engine import IndicatorEngine
from app.services.regime_engine import RegimeEngine
from app.services.risk_engine import RiskEngine
from app.services.strategy_engine import StrategyEngine
from app.services.contract_registry import ContractRegistry
from app.utils.spread_helpers import price_to_bp, bp_to_price, compute_spread_bar
from app.utils.math_helpers import round_to_tick, price_to_ticks, compute_max_lots, compute_rr_ratio
from app.utils.validation_helpers import validate_ohlcv_bar, validate_bar_series, ValidationError

SETTINGS = {"indicators": {"atr_length": 14, "ma_fast": 5, "ma_slow": 10, "donchian_length": 10, "bollinger_length": 10, "bollinger_std": 2.0, "dcw_length": 10, "spread_sma_length": 10, "min_bars_required": 20}, "risk": {"max_risk_per_trade": 500, "max_lots": 20, "max_daily_risk": 2500, "event_risk_multiplier": 0.5, "default_slippage_ticks": 1, "default_commission_per_lot": 2.50}, "regime": {"trend_ma_separation_threshold": 0.010, "range_atr_percentile_threshold": 30, "volatility_atr_multiplier": 1.5, "event_lock_window_hours": 4, "regime_expiration_hours": 24}, "volatility": {"low_vol_threshold": 0.8, "high_vol_threshold": 1.8}, "scoring": {"min_confidence_threshold": 0.3, "high_confidence_threshold": 0.7, "caution_threshold": 0.5, "conflicting_strategy_penalty": 0.15}, "sizing": {"scale_in_levels": 3, "scale_in_ratios": [0.5, 0.3, 0.2], "target_levels": 3, "target_ratios": [0.5, 0.3, 0.2]}}

_BASE_DT = datetime(2026, 1, 1, tzinfo=timezone.utc)

def _make_bars(count, base=96.5):
    return [OHLCVBar(timestamp=_BASE_DT + timedelta(hours=i), open=base+i*0.005, high=base+i*0.005+0.01, low=base+i*0.005-0.005, close=base+i*0.005+0.002, volume=100, timeframe=Timeframe.H1, product="FFN26") for i in range(count)]

# ── Spread Math ───────────────────────────────────────
class TestSpreadMath:
    def test_price_to_bp(self):
        assert price_to_bp(96.500, 96.450) == 5.0
    def test_bp_to_price(self):
        assert bp_to_price(5.0) == 0.05
    def test_negative_spread(self):
        assert price_to_bp(96.400, 96.500) == -10.0
    def test_compute_spread_bar(self):
        front = OHLCVBar(timestamp=datetime(2026,1,1,tzinfo=timezone.utc), open=96.5, high=96.51, low=96.49, close=96.505, volume=100, timeframe=Timeframe.H1, product="FFN26")
        back = OHLCVBar(timestamp=datetime(2026,1,1,tzinfo=timezone.utc), open=96.45, high=96.46, low=96.44, close=96.455, volume=80, timeframe=Timeframe.H1, product="FFQ26")
        sb = compute_spread_bar(front, back, "FFN26-FFQ26")
        assert sb.close_bp == 5.0

# ── Math Helpers ──────────────────────────────────────
class TestMathHelpers:
    def test_round_to_tick(self):
        assert round_to_tick(96.503, 0.005) == 96.505
    def test_price_to_ticks(self):
        assert price_to_ticks(0.050, 0.005) == 10
    def test_max_lots(self):
        assert compute_max_lots(500, 10, 20.835) == 2
    def test_rr_ratio(self):
        assert compute_rr_ratio(96.5, 96.45, 96.6) == 2.0

# ── Validation ────────────────────────────────────────
class TestValidation:
    def test_valid_bar(self):
        bar = OHLCVBar(timestamp=datetime(2026,1,1,tzinfo=timezone.utc), open=96.5, high=96.51, low=96.49, close=96.505, volume=100, timeframe=Timeframe.H1, product="FFN26")
        warnings = validate_ohlcv_bar(bar)
        assert isinstance(warnings, list)
    def test_insufficient_bars(self):
        bars = _make_bars(5)
        warnings, errors = validate_bar_series(bars, min_bars=20)
        assert len(errors) > 0
    def test_zero_volume_warning(self):
        bar = OHLCVBar(timestamp=datetime(2026,1,1,tzinfo=timezone.utc), open=96.5, high=96.51, low=96.49, close=96.505, volume=0, timeframe=Timeframe.H1, product="FFN26")
        warnings = validate_ohlcv_bar(bar)
        assert any("volume" in w.field for w in warnings)

# ── Regime Engine ─────────────────────────────────────
class TestRegimeEngine:
    def test_manual_override(self):
        engine = RegimeEngine(SETTINGS)
        state = engine.update(RegimeUpdateRequest(regime=MarketRegime.TREND, macro_bias=MacroBias.HAWKISH))
        assert state.regime == MarketRegime.TREND
        assert state.is_manual_override
    def test_trend_classification(self):
        engine = RegimeEngine(SETTINGS)
        # MA separation = |97.5 - 96.5| / 96.5 = 0.01036 > 0.010 threshold
        state = engine.classify(RegimeClassificationInput(current_atr=0.01, atr_percentile=50, ma_fast=97.5, ma_slow=96.5, price=96.5, donchian_upper=97.0, donchian_lower=96.0, dcw=1.0))
        assert state.regime == MarketRegime.TREND
    def test_range_classification(self):
        engine = RegimeEngine(SETTINGS)
        state = engine.classify(RegimeClassificationInput(current_atr=0.002, atr_percentile=10, ma_fast=96.5, ma_slow=96.5, price=96.5, donchian_upper=96.6, donchian_lower=96.4, dcw=0.2))
        assert state.regime == MarketRegime.RANGE

# ── Strategy Engine ───────────────────────────────────
class TestStrategyEngine:
    def _make_engine(self):
        return StrategyEngine(IndicatorEngine(SETTINGS), RegimeEngine(SETTINGS), RiskEngine(SETTINGS), SETTINGS)
    def test_evaluate_all_with_data(self):
        engine = self._make_engine()
        bars = _make_bars(60)
        response = engine.evaluate_all(bars=bars, product="FFN26", contract_type=ContractType.OUTRIGHT, timeframe=Timeframe.H1)
        assert len(response.strategies_evaluated) > 0
        assert response.evaluation_time_ms >= 0
    def test_evaluate_no_data(self):
        engine = self._make_engine()
        response = engine.evaluate_all(bars=[], product="FFN26")
        assert len(response.signals) == 0
    def test_select_strategy(self):
        engine = self._make_engine()
        bars = _make_bars(60)
        response = engine.evaluate_all(bars=bars, product="FFN26", contract_type=ContractType.OUTRIGHT)
        result = engine.select_strategy(response)
        # May or may not have a signal depending on data
        assert result is None or result.confidence_score >= 0

# ── Contract Registry ─────────────────────────────────
class TestContractRegistry:
    def test_load(self):
        config = {"contracts": [{"symbol": "FFN26", "type": "outright", "tick_size": 0.005, "tick_value": 20.835, "contract_value": 4167}, {"symbol": "FFN26-FFQ26", "type": "spread", "front_contract": "FFN26", "back_contract": "FFQ26", "tick_size_bp": 0.5, "tick_value": 20.835}]}
        reg = ContractRegistry(config)
        assert reg.is_registered("FFN26")
        assert reg.is_registered("FFN26-FFQ26")
        assert reg.get_contract_type("FFN26") == ContractType.OUTRIGHT
        assert reg.get_spread_legs("FFN26-FFQ26") == ("FFN26", "FFQ26")

# ── Latency Benchmark ─────────────────────────────────
class TestLatency:
    def test_indicator_latency(self):
        import time
        engine = IndicatorEngine(SETTINGS)
        bars = _make_bars(200)
        engine.compute(bars, "FFN26")  # warm cache
        start = time.perf_counter()
        engine.compute(bars, "FFN26")
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 5, f"Cache hit took {elapsed_ms:.2f}ms, target <5ms"
