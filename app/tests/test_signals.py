"""Tests for signal generation and signal cards."""
import pytest

from app.contracts.signals import (
    Signal,
    SignalDirection,
    SignalStrength,
    StrategySignal,
    SignalCard,
)


class TestSignalModels:
    def test_signal_defaults(self):
        sig = Signal()
        assert sig.direction == SignalDirection.FLAT
        assert sig.strength == SignalStrength.NEUTRAL
        assert sig.confidence == 0.0

    def test_strategy_signal_creation(self):
        sig = StrategySignal(
            strategy_name="test",
            symbol="FFN26",
            timeframe="1H",
            direction=SignalDirection.LONG,
            strength=SignalStrength.BUY,
            confidence=0.75,
            entry_price=95.750,
            stop_price=95.700,
            target_price=95.900,
            risk_reward_ratio=3.0,
            rationale="Test signal",
        )
        assert sig.strategy_name == "test"
        assert sig.confidence == 0.75

    def test_signal_card_creation(self):
        sig = StrategySignal(
            strategy_name="test",
            symbol="FFN26",
            timeframe="1H",
            direction=SignalDirection.LONG,
            confidence=0.8,
        )
        card = SignalCard(
            symbol="FFN26",
            product_key="fed_funds",
            instrument_type="outright",
            signals=[sig],
            best_signal=sig,
            overall_direction=SignalDirection.LONG,
            overall_confidence=0.8,
            last_price=95.750,
        )
        assert card.symbol == "FFN26"
        assert len(card.signals) == 1
        assert card.overall_confidence == 0.8

    def test_confidence_clamped(self):
        sig = Signal(confidence=0.5)
        assert 0.0 <= sig.confidence <= 1.0

        with pytest.raises(Exception):
            Signal(confidence=1.5)

        with pytest.raises(Exception):
            Signal(confidence=-0.1)
