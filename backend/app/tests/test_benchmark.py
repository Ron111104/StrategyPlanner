"""Latency benchmark tests for performance-critical paths."""

import time
import pytest

from app.services.indicator_engine import IndicatorEngine
from app.services.risk_engine import RiskEngine
from app.contracts.execution_inputs import PositionSizingRequest, AccountConfig


class TestBenchmarks:
    def test_indicator_computation_latency(self, indicator_engine, sample_bars):
        """All indicators should compute in under 50ms for 60 bars."""
        config = {
            "atr": {"length": 14},
            "sma": {"lengths": [10, 20, 50]},
            "ema": {"lengths": [9, 21, 50]},
            "donchian": {"length": 20},
            "bollinger": {"length": 20, "std_dev": 2.0},
            "dcw": {"length": 20},
        }

        start = time.perf_counter()
        for _ in range(10):
            indicator_engine.compute_all(sample_bars, config)
        elapsed = (time.perf_counter() - start) / 10 * 1000  # Average ms

        assert elapsed < 50, f"Indicator computation took {elapsed:.1f}ms, expected < 50ms"

    def test_risk_profile_latency(self, risk_engine):
        """Risk profile computation should be under 5ms."""
        start = time.perf_counter()
        for _ in range(100):
            risk_engine.compute_risk_profile(
                entry_price=96.500,
                stop_price=96.450,
                target_price=96.600,
                position_size=5,
                direction="long",
                tick_size=0.005,
                tick_value=20.835,
            )
        elapsed = (time.perf_counter() - start) / 100 * 1000  # Average ms

        assert elapsed < 5, f"Risk profile took {elapsed:.1f}ms, expected < 5ms"

    def test_position_sizing_latency(self, risk_engine, sample_account_config):
        """Position sizing should be under 2ms."""
        request = PositionSizingRequest(
            account_config=sample_account_config,
            entry_price=96.500,
            stop_price=96.450,
            contract_tick_size=0.005,
            contract_tick_value=20.835,
            is_spread=False,
            is_event_window=False,
        )

        start = time.perf_counter()
        for _ in range(100):
            risk_engine.compute_position_size(request)
        elapsed = (time.perf_counter() - start) / 100 * 1000

        assert elapsed < 2, f"Position sizing took {elapsed:.1f}ms, expected < 2ms"

    def test_ladder_generation_latency(self, risk_engine):
        """Ladder generation should be under 5ms."""
        start = time.perf_counter()
        for _ in range(100):
            risk_engine.generate_ladder(
                entry_price=96.500,
                stop_price=96.450,
                target_price=96.600,
                total_size=10,
                num_levels=3,
                tick_size=0.005,
                direction="long",
            )
        elapsed = (time.perf_counter() - start) / 100 * 1000

        assert elapsed < 5, f"Ladder generation took {elapsed:.1f}ms, expected < 5ms"
