"""Tests for the RiskEngine."""

import pytest

from app.services.risk_engine import RiskEngine
from app.contracts.execution_inputs import AccountConfig, PositionSizingRequest


class TestRiskEngine:
    def test_compute_risk_profile_long(self, risk_engine):
        """Risk profile for a long trade."""
        profile = risk_engine.compute_risk_profile(
            entry_price=96.500,
            stop_price=96.450,
            target_price=96.600,
            position_size=5,
            direction="long",
            tick_size=0.005,
            tick_value=20.835,
        )
        assert profile.direction == "long"
        assert profile.tick_risk == 10
        assert profile.dollar_risk > 0
        assert profile.dollar_target > 0
        assert profile.risk_reward_ratio > 0
        assert profile.total_cost >= 0

    def test_compute_risk_profile_short(self, risk_engine):
        """Risk profile for a short trade."""
        profile = risk_engine.compute_risk_profile(
            entry_price=96.500,
            stop_price=96.550,
            target_price=96.400,
            position_size=3,
            direction="short",
            tick_size=0.005,
            tick_value=20.835,
        )
        assert profile.direction == "short"
        assert profile.tick_risk == 10
        assert profile.dollar_risk > 0

    def test_position_sizing_basic(self, risk_engine, sample_account_config):
        """Basic position sizing computation."""
        request = PositionSizingRequest(
            account_config=sample_account_config,
            entry_price=96.500,
            stop_price=96.450,
            contract_tick_size=0.005,
            contract_tick_value=20.835,
            is_spread=False,
            is_event_window=False,
        )
        size = risk_engine.compute_position_size(request)
        assert isinstance(size, int)
        assert size >= 1
        assert size <= sample_account_config.max_position_size

    def test_position_sizing_event_reduction(self, risk_engine, sample_account_config):
        """Position size should be smaller during event window."""
        normal_request = PositionSizingRequest(
            account_config=sample_account_config,
            entry_price=96.500,
            stop_price=96.450,
            contract_tick_size=0.005,
            contract_tick_value=20.835,
            is_spread=False,
            is_event_window=False,
        )
        event_request = PositionSizingRequest(
            account_config=sample_account_config,
            entry_price=96.500,
            stop_price=96.450,
            contract_tick_size=0.005,
            contract_tick_value=20.835,
            is_spread=False,
            is_event_window=True,
        )

        normal_size = risk_engine.compute_position_size(normal_request)
        event_size = risk_engine.compute_position_size(event_request)
        assert event_size <= normal_size

    def test_position_sizing_max_cap(self, risk_engine):
        """Position size should not exceed max_position_size."""
        config = AccountConfig(
            account_size_usd=10_000_000.0,
            risk_per_trade_usd=100_000.0,
            max_risk_per_trade_usd=100_000.0,
            max_position_size=50,
            slippage_ticks=1,
            commission_per_side=2.50,
            event_risk_reduction=0.5,
        )
        request = PositionSizingRequest(
            account_config=config,
            entry_price=96.500,
            stop_price=96.495,
            contract_tick_size=0.005,
            contract_tick_value=20.835,
            is_spread=False,
            is_event_window=False,
        )
        size = risk_engine.compute_position_size(request)
        assert size <= 50

    def test_generate_ladder(self, risk_engine):
        """Ladder generation should produce entry, stop, and target levels."""
        ladder = risk_engine.generate_ladder(
            entry_price=96.500,
            stop_price=96.450,
            target_price=96.600,
            total_size=10,
            num_levels=3,
            tick_size=0.005,
            direction="long",
        )
        assert len(ladder.entry_levels) > 0
        assert len(ladder.stop_levels) > 0
        assert len(ladder.target_levels) > 0
        assert ladder.total_size == 10

    def test_round_trip_cost(self, risk_engine):
        """Round trip cost should include slippage and commission."""
        cost = risk_engine.compute_round_trip_cost(
            position_size=5,
            slippage_ticks=1,
            tick_value=20.835,
            commission_per_side=2.50,
        )
        assert cost > 0
        expected_slippage = 1 * 20.835 * 5 * 2  # ticks * value * size * 2 (round trip)
        expected_commission = 2.50 * 2 * 5
        assert abs(cost - (expected_slippage + expected_commission)) < 0.01

    def test_risk_reward_ratio(self, risk_engine):
        """R:R ratio should be correctly computed."""
        profile = risk_engine.compute_risk_profile(
            entry_price=96.500,
            stop_price=96.450,
            target_price=96.650,
            position_size=1,
            direction="long",
            tick_size=0.005,
            tick_value=20.835,
        )
        # Target is 30 ticks, stop is 10 ticks, R:R should be ~3:1
        assert profile.risk_reward_ratio > 2.5
