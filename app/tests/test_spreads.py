"""Tests for spread computation and quoting."""
import pytest
from datetime import datetime

from app.contracts.market_data import SpreadQuote
from app.utils.helpers import spread_bp_from_prices


class TestSpreadComputation:
    def test_spread_bp_positive(self):
        result = SpreadQuote.compute_spread_bp(95.750, 95.700)
        assert result == 5.0

    def test_spread_bp_negative(self):
        result = SpreadQuote.compute_spread_bp(95.700, 95.750)
        assert result == -5.0

    def test_spread_bp_zero(self):
        result = SpreadQuote.compute_spread_bp(95.750, 95.750)
        assert result == 0.0

    def test_spread_bp_large(self):
        result = SpreadQuote.compute_spread_bp(96.000, 95.500)
        assert result == 50.0

    def test_spread_bp_fractional(self):
        result = SpreadQuote.compute_spread_bp(95.755, 95.750)
        assert result == 0.5


class TestSpreadQuote:
    def test_spread_quote_creation(self):
        quote = SpreadQuote(
            spread_symbol="FFN26-FFQ26",
            front_leg="FFN26",
            back_leg="FFQ26",
            front_price=95.750,
            back_price=95.700,
            spread_bp=5.0,
            product_key="fed_funds",
        )
        assert quote.spread_symbol == "FFN26-FFQ26"
        assert quote.spread_bp == 5.0

    def test_spread_quote_negative_spread(self):
        front = 95.700
        back = 95.850
        bp = SpreadQuote.compute_spread_bp(front, back)
        quote = SpreadQuote(
            spread_symbol="FFN26-FFQ26",
            front_leg="FFN26",
            back_leg="FFQ26",
            front_price=front,
            back_price=back,
            spread_bp=bp,
            product_key="fed_funds",
        )
        assert quote.spread_bp == -15.0


class TestHelperSpreadBp:
    def test_spread_bp_from_prices(self):
        assert spread_bp_from_prices(95.750, 95.700) == 5.0
        assert spread_bp_from_prices(95.700, 95.750) == -5.0
        assert spread_bp_from_prices(96.000, 95.000) == 100.0


class TestSpreadConventions:
    def test_one_price_point_equals_100_bp(self):
        """Verify: 1 full price point = 100 basis points."""
        front = 96.000
        back = 95.000
        bp = SpreadQuote.compute_spread_bp(front, back)
        assert bp == 100.0

    def test_half_point_equals_50_bp(self):
        front = 95.750
        back = 95.250
        bp = SpreadQuote.compute_spread_bp(front, back)
        assert bp == 50.0

    def test_tick_size_consistency(self):
        """One outright tick (0.005) = 0.5 bp."""
        front = 95.755
        back = 95.750
        bp = SpreadQuote.compute_spread_bp(front, back)
        assert bp == 0.5
