"""Regime classification engine."""
from typing import Optional

from app.contracts.indicators import IndicatorSet
from app.contracts.regime import MacroBias, RegimeState, RegimeType
from app.core.logging import get_logger
from app.services.cache import CacheManager

logger = get_logger(__name__)


class RegimeEngine:
    """Manages regime state and provides regime-based context for strategies."""

    def __init__(self) -> None:
        self._cache = CacheManager()

    def get_current_regime(self) -> RegimeState:
        """Get the current manually-set regime state."""
        return self._cache.get_regime()

    def set_regime(
        self,
        regime: RegimeType,
        macro_bias: MacroBias,
        notes: str = "",
    ) -> RegimeState:
        """Manually set the regime state."""
        state = self._cache.set_regime(regime, macro_bias, notes)
        logger.info(
            "regime_updated",
            regime=regime.value,
            macro_bias=macro_bias.value,
            notes=notes,
        )
        return state

    def suggest_regime(self, indicators: IndicatorSet) -> dict[str, float]:
        """Provide regime suggestions based on indicator data (advisory only).

        Returns a dict of regime -> confidence score (0-1).
        The trader always makes the final decision.
        """
        scores: dict[str, float] = {
            "trend": 0.0,
            "range": 0.0,
            "volatility": 0.0,
            "event": 0.0,
        }

        # DCW-based regime suggestion
        if indicators.dcw and indicators.dcw.values:
            dcw_values = indicators.dcw.values
            if len(dcw_values) >= 10:
                recent_dcw = dcw_values[-1]
                avg_dcw = sum(dcw_values[-20:]) / min(len(dcw_values), 20)

                if avg_dcw > 0:
                    dcw_ratio = recent_dcw / avg_dcw
                else:
                    dcw_ratio = 1.0

                if dcw_ratio > 1.5:
                    scores["trend"] = min(0.9, dcw_ratio / 2.0)
                    scores["volatility"] = min(0.7, (dcw_ratio - 1.0))
                elif dcw_ratio < 0.6:
                    scores["range"] = min(0.9, (1.0 - dcw_ratio) * 1.5)
                else:
                    scores["range"] = 0.5
                    scores["trend"] = 0.3

        # ATR-based volatility signal
        if indicators.atr and indicators.atr.values:
            atr_values = indicators.atr.values
            if len(atr_values) >= 10:
                recent_atr = atr_values[-1]
                avg_atr = sum(atr_values[-20:]) / min(len(atr_values), 20)

                if avg_atr > 0:
                    atr_ratio = recent_atr / avg_atr
                    if atr_ratio > 2.0:
                        scores["volatility"] = max(scores["volatility"], 0.8)
                        scores["event"] = max(scores["event"], 0.6)

        # EMA trend alignment
        ema_short = indicators.ema.get(9)
        ema_long = indicators.ema.get(21)
        if ema_short and ema_long and ema_short.values and ema_long.values:
            if ema_short.values[-1] > ema_long.values[-1]:
                scores["trend"] = max(scores["trend"], 0.6)
            elif abs(ema_short.values[-1] - ema_long.values[-1]) < 0.01:
                scores["range"] = max(scores["range"], 0.6)

        return scores

    def is_strategy_applicable(
        self, strategy_regimes: list[str], strategy_timeframes: list[str], timeframe: str
    ) -> bool:
        """Check if a strategy is applicable given current regime and timeframe."""
        current = self.get_current_regime()
        regime_match = current.regime.value in strategy_regimes
        tf_match = timeframe in strategy_timeframes
        return regime_match and tf_match
