"""Tests for Risk Engine — sizing, ladders, and cost calculations."""
import pytest
from app.contracts.execution_inputs import AccountConfig, RiskCalcInput
from app.contracts.market_data import ContractType
from app.services.risk_engine import RiskEngine

SETTINGS = {"risk": {"max_risk_per_trade": 500, "max_lots": 20, "max_daily_risk": 2500, "event_risk_multiplier": 0.5, "default_slippage_ticks": 1, "default_commission_per_lot": 2.50}, "sizing": {"scale_in_levels": 3, "scale_in_ratios": [0.5, 0.3, 0.2], "target_levels": 3, "target_ratios": [0.5, 0.3, 0.2]}}

class TestRiskEngine:
    def test_basic_risk_calc(self):
        engine = RiskEngine(SETTINGS)
        result = engine.compute_risk(RiskCalcInput(entry_price=96.500, stop_price=96.450, contract_type=ContractType.OUTRIGHT, tick_size=0.005, tick_value=20.835))
        assert result.stop_distance_ticks == 10
        assert result.dollar_risk_per_lot > 0
        assert result.max_lots > 0

    def test_event_risk_reduction(self):
        engine = RiskEngine(SETTINGS)
        normal = engine.compute_risk(RiskCalcInput(entry_price=96.500, stop_price=96.450, tick_size=0.005, tick_value=20.835, contract_type=ContractType.OUTRIGHT))
        event = engine.compute_risk(RiskCalcInput(entry_price=96.500, stop_price=96.450, tick_size=0.005, tick_value=20.835, contract_type=ContractType.OUTRIGHT, is_event_regime=True))
        assert event.event_adjusted
        assert event.effective_max_risk < normal.effective_max_risk

    def test_zero_stop_distance(self):
        engine = RiskEngine(SETTINGS)
        result = engine.compute_risk(RiskCalcInput(entry_price=96.500, stop_price=96.500, tick_size=0.005, tick_value=20.835, contract_type=ContractType.OUTRIGHT))
        assert result.max_lots == 0

    def test_ladder_generation(self):
        engine = RiskEngine(SETTINGS)
        ladder = engine.build_ladder(entry_price=96.500, stop_price=96.450, targets=[96.550, 96.600, 96.700], total_lots=10, tick_size=0.005, tick_value=20.835, direction="long")
        assert len(ladder.entry_levels) > 0
        assert len(ladder.target_levels) > 0
        assert ladder.total_lots > 0

    def test_commission_calculation(self):
        engine = RiskEngine(SETTINGS)
        result = engine.compute_risk(RiskCalcInput(entry_price=96.500, stop_price=96.450, tick_size=0.005, tick_value=20.835, contract_type=ContractType.OUTRIGHT))
        assert result.total_commission > 0
        assert result.round_trip_cost > 0

    def test_account_update(self):
        engine = RiskEngine(SETTINGS)
        new_config = AccountConfig(max_risk_per_trade=1000, max_lots=50)
        engine.update_account(new_config)
        assert engine.account_config.max_risk_per_trade == 1000

    def test_rr_ratio(self):
        engine = RiskEngine(SETTINGS)
        result = engine.compute_risk(RiskCalcInput(entry_price=96.500, stop_price=96.450, tick_size=0.005, tick_value=20.835, contract_type=ContractType.OUTRIGHT), targets=[96.600])
        assert result.risk_reward_ratio is not None
        assert result.risk_reward_ratio == 2.0
