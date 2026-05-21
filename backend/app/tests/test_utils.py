"""Tests for utility functions."""

import pytest
from datetime import datetime, timedelta, timezone

from app.utils.math_helpers import (
    round_to_tick,
    ticks_between,
    dollar_value_of_ticks,
    wilder_smooth,
    safe_divide,
    percentage_change,
)
from app.utils.spread_helpers import (
    price_to_spread_bp,
    spread_bp_to_ticks,
    spread_ticks_to_dollar,
    implied_rate_from_price,
    price_from_implied_rate,
    rate_change_bp,
)
from app.utils.datetime_helpers import (
    now_utc,
    is_within_event_window,
    timeframe_to_seconds,
)
from app.utils.validation_helpers import validate_bars_minimum


class TestMathHelpers:
    def test_round_to_tick(self):
        assert round_to_tick(96.503, 0.005) == 96.505
        assert round_to_tick(96.502, 0.005) == 96.500
        assert round_to_tick(96.500, 0.005) == 96.500

    def test_ticks_between(self):
        result = ticks_between(96.500, 96.450, 0.005)
        assert result == 10

        result = ticks_between(96.450, 96.500, 0.005)
        assert result == 10  # Should be absolute

    def test_dollar_value_of_ticks(self):
        result = dollar_value_of_ticks(10, 20.835)
        assert abs(result - 208.35) < 0.01

    def test_percentage_change(self):
        result = percentage_change(95.0, 96.0)
        assert abs(result - 1.0526) < 0.01

    def test_wilder_smooth(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        result = wilder_smooth(values, 3)
        assert isinstance(result, list)
        assert len(result) == len(values)

    def test_safe_divide(self):
        assert safe_divide(10, 2) == 5.0
        assert safe_divide(10, 0) == 0.0
        assert safe_divide(10, 0, default=-1.0) == -1.0


class TestSpreadHelpers:
    def test_price_to_spread_bp(self):
        result = price_to_spread_bp(96.500, 96.450)
        assert abs(result - 5.0) < 0.01

    def test_price_to_spread_bp_negative(self):
        result = price_to_spread_bp(96.400, 96.500)
        assert result < 0

    def test_spread_bp_to_ticks(self):
        result = spread_bp_to_ticks(5.0, 0.5)
        assert result == 10.0

    def test_spread_ticks_to_dollar(self):
        result = spread_ticks_to_dollar(10.0, 20.835)
        assert abs(result - 208.35) < 0.01

    def test_implied_rate_from_price(self):
        assert abs(implied_rate_from_price(96.500) - 3.500) < 0.001

    def test_price_from_implied_rate(self):
        assert abs(price_from_implied_rate(3.500) - 96.500) < 0.001

    def test_rate_change_bp(self):
        result = rate_change_bp(96.500, 96.450)
        # Price drop = rate increase = positive bp change
        assert abs(result - 5.0) < 0.1


class TestDatetimeHelpers:
    def test_now_utc(self):
        result = now_utc()
        assert result.tzinfo is not None

    def test_is_within_event_window(self):
        event_time = datetime.now(timezone.utc) + timedelta(hours=2)
        current_time = datetime.now(timezone.utc)
        assert is_within_event_window(event_time, current_time, window_hours=4) is True

    def test_is_outside_event_window(self):
        event_time = datetime.now(timezone.utc) - timedelta(hours=10)
        current_time = datetime.now(timezone.utc)
        assert is_within_event_window(event_time, current_time, window_hours=4) is False

    def test_timeframe_to_seconds(self):
        assert timeframe_to_seconds("1M") == 60
        assert timeframe_to_seconds("5M") == 300
        assert timeframe_to_seconds("1H") == 3600
        assert timeframe_to_seconds("1D") == 86400


class TestValidationHelpers:
    def test_validate_bars_minimum_pass(self, sample_bars):
        result = validate_bars_minimum(sample_bars, 51, "test")
        assert result is True

    def test_validate_bars_minimum_fail(self, sample_bars_short):
        with pytest.raises((ValueError, Exception)):
            validate_bars_minimum(sample_bars_short, 51, "test")
