"""Base strategy interface."""
from abc import ABC, abstractmethod
from typing import Optional

from app.contracts.indicators import IndicatorSet
from app.contracts.market_data import OHLCVSeries
from app.contracts.regime import RegimeState
from app.contracts.signals import SignalDirection, SignalStrength, StrategySignal
from app.contracts.strategy import EntryExitPlan


class BaseStrategy(ABC):
    """Abstract base class for all strategies."""

    name: str = "base"
    display_name: str = "Base Strategy"

    @abstractmethod
    def evaluate(
        self,
        series: OHLCVSeries,
        indicators: IndicatorSet,
        regime: RegimeState,
        product_config: dict,
    ) -> Optional[StrategySignal]:
        """Evaluate strategy and return a signal if conditions are met."""
        ...

    @abstractmethod
    def build_entry_exit_plan(
        self,
        signal: StrategySignal,
        series: OHLCVSeries,
        indicators: IndicatorSet,
        product_config: dict,
    ) -> Optional[EntryExitPlan]:
        """Build entry/exit plan from a signal."""
        ...

    def should_disable(
        self,
        series: OHLCVSeries,
        indicators: IndicatorSet,
        regime: RegimeState,
    ) -> tuple[bool, str]:
        """Check if strategy should be disabled. Returns (disabled, reason)."""
        if series.is_empty:
            return True, "No market data available"
        if series.length < 20:
            return True, f"Insufficient bars: {series.length} < 20"
        return False, ""

    @staticmethod
    def _classify_strength(confidence: float) -> SignalStrength:
        if confidence >= 0.8:
            return SignalStrength.STRONG_BUY
        elif confidence >= 0.6:
            return SignalStrength.BUY
        elif confidence <= 0.2:
            return SignalStrength.STRONG_SELL
        elif confidence <= 0.4:
            return SignalStrength.SELL
        return SignalStrength.NEUTRAL
