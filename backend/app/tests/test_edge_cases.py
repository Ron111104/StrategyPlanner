"""Tests for edge cases across the platform."""

import pytest
from datetime import datetime, timedelta, timezone

from app.contracts.market_data import OHLCVBar, Timeframe
from app.contracts.execution_inputs import AccountConfig, PositionSizingRequest
from app.utils.spread_helpers import price_to_spread_bp


class TestEdgeCases:
    def test_empty_bars_list(self, indicator_engine):
        """Empty bar list should raise an error."""
        with pytest.raises(Exception):
            indicator_engine.compute_atr([], length=14)

    def test_single_bar(self, indicator_engine):
        """Single bar should raise insufficient data error."""
        bar = OHLCVBar(
            timestamp=datetime.now(timezone.utc),
            open=96.500, high=96.510, low=96.490, close=96.505,
            volume=100, timeframe=Timeframe("1H"), product="FFN25",
        )
        with pytest.raises(Exception):
            indicator_engine.compute_atr([bar], length=14)

    def test_minimum_bars_boundary(self, indicator_engine):
        """Exactly minimum bars should work without error."""
        bars = []
        for i in range(15):
            bars.append(OHLCVBar(
                timestamp=datetime.now(timezone.utc) + timedelta(hours=i),
                open=96.500 + i * 0.001,
                high=96.510 + i * 0.001,
                low=96.490 + i * 0.001,
                close=96.505 + i * 0.001,
                volume=100,
                timeframe=Timeframe("1H"),
                product="FFN25",
            ))
        # 15 bars should be enough for ATR(14)
        atr = indicator_engine.compute_atr(bars, length=14)
        assert len(atr) == 15

    def test_negative_spread(self):
        """Negative spread should be handled correctly."""
        spread = price_to_spread_bp(96.400, 96.500)
        assert spread < 0
        assert abs(spread - (-10.0)) < 0.1

    def test_zero_volume_bar(self, indicator_engine):
        """Bars with zero volume should still compute indicators."""
        bars = []
        for i in range(20):
            bars.append(OHLCVBar(
                timestamp=datetime.now(timezone.utc) + timedelta(hours=i),
                open=96.500, high=96.510, low=96.490, close=96.505,
                volume=0,
                timeframe=Timeframe("1H"),
                product="FFN25",
            ))
        sma = indicator_engine.compute_sma([b.close for b in bars], length=10)
        assert len(sma) == 20

    def test_same_entry_stop(self, risk_engine):
        """Same entry and stop should not divide by zero."""
        profile = risk_engine.compute_risk_profile(
            entry_price=96.500,
            stop_price=96.500,
            target_price=96.600,
            position_size=1,
            direction="long",
            tick_size=0.005,
            tick_value=20.835,
        )
        # Should handle gracefully
        assert profile.tick_risk == 0

    def test_very_large_position(self, risk_engine):
        """Large position should be capped."""
        config = AccountConfig(
            account_size_usd=1_000_000,
            risk_per_trade_usd=500_000,
            max_risk_per_trade_usd=500_000,
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
