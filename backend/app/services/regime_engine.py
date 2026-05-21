"""
Regime classification engine for CME Fed Funds Futures (ZQ) Strategy Planning Platform.

Determines the current market regime (event, volatility, trend, range)
based on indicator state, macro events, and manual overrides.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import numpy as np
import structlog

from app.contracts.market_data import OHLCVBar
from app.contracts.macro_inputs import (
    MacroBias,
    MacroEvent,
    MarketRegime,
    RegimeState,
    RegimeUpdateRequest,
)
from app.core.exceptions import InsufficientDataError, RegimeNotSetError
from app.utils.datetime_helpers import is_within_event_window, now_utc

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ── Default thresholds (can be overridden via strategy_settings.yaml) ──
_DEFAULT_VOLATILITY_ATR_THRESHOLD: float = 1.5
_DEFAULT_TREND_ATR_THRESHOLD: float = 1.15
_DEFAULT_RANGE_DCW_THRESHOLD: float = 0.005
_DEFAULT_EVENT_WINDOW_HOURS: int = 4


class RegimeEngine:
    """Classifies and caches the market regime per product."""

    __slots__ = (
        "_regime_cache",
        "_volatility_atr_threshold",
        "_trend_atr_threshold",
        "_range_dcw_threshold",
        "_event_window_hours",
    )

    def __init__(
        self,
        *,
        volatility_atr_threshold: float = _DEFAULT_VOLATILITY_ATR_THRESHOLD,
        trend_atr_threshold: float = _DEFAULT_TREND_ATR_THRESHOLD,
        range_dcw_threshold: float = _DEFAULT_RANGE_DCW_THRESHOLD,
        event_window_hours: int = _DEFAULT_EVENT_WINDOW_HOURS,
    ) -> None:
        self._regime_cache: dict[str, RegimeState] = {}
        self._volatility_atr_threshold = volatility_atr_threshold
        self._trend_atr_threshold = trend_atr_threshold
        self._range_dcw_threshold = range_dcw_threshold
        self._event_window_hours = event_window_hours

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def classify_regime(
        self,
        product: str,
        bars: list[OHLCVBar],
        indicators: dict[str, Any],
        events: list[MacroEvent] | None = None,
    ) -> RegimeState:
        """Classify regime with priority: event > volatility > trend > range.

        Parameters
        ----------
        product:
            Product symbol, e.g. ``"ZQM2026"``.
        bars:
            Recent OHLCV bars.
        indicators:
            Output of ``IndicatorEngine.compute_all``.
        events:
            Optional upcoming / recent macro events.

        Returns
        -------
        RegimeState
            The classified regime state (stored in cache).
        """
        log = logger.bind(product=product)

        # ── 1. Event check (highest priority) ──
        if events and self._is_event_active(events):
            regime = MarketRegime.EVENT
            bias = self._classify_macro_bias(bars, indicators)
            confidence = 0.95
            reason = "Active macro event detected within event window"
            log.info(
                "regime_classified",
                regime=regime.value,
                reason=reason,
                bias=bias.value,
            )
            state = RegimeState(
                regime=regime,
                bias=bias,
                confidence=confidence,
                reason=reason,
                classified_at=now_utc(),
                is_override=False,
            )
            self._regime_cache[product] = state
            return state

        # ── Extract latest indicator values ──
        atr_series: list[float] = indicators.get("atr", [])
        atr_sma_series: list[float] = indicators.get("atr_sma", [])
        sma_series: list[float] = indicators.get("sma", [])
        dcw_series: list[float] = indicators.get("dcw", [])

        latest_atr = self._last_valid(atr_series)
        latest_atr_sma = self._last_valid(atr_sma_series)
        latest_sma = self._last_valid(sma_series)
        latest_dcw = self._last_valid(dcw_series)
        latest_close = bars[-1].close if bars else None

        # ── 2. Volatility regime ──
        if (
            latest_atr is not None
            and latest_atr_sma is not None
            and latest_atr_sma > 0
            and latest_atr > latest_atr_sma * self._volatility_atr_threshold
        ):
            regime = MarketRegime.VOLATILITY
            bias = self._classify_macro_bias(bars, indicators)
            ratio = latest_atr / latest_atr_sma
            confidence = min(0.90, 0.60 + (ratio - self._volatility_atr_threshold) * 0.20)
            reason = (
                f"ATR ({latest_atr:.6f}) exceeds ATR-SMA * "
                f"{self._volatility_atr_threshold} ({latest_atr_sma * self._volatility_atr_threshold:.6f})"
            )
            log.info("regime_classified", regime=regime.value, reason=reason, bias=bias.value)
            state = RegimeState(
                regime=regime,
                bias=bias,
                confidence=confidence,
                reason=reason,
                classified_at=now_utc(),
                is_override=False,
            )
            self._regime_cache[product] = state
            return state

        # ── 3. Trend regime ──
        if (
            latest_close is not None
            and latest_sma is not None
            and latest_atr is not None
            and latest_atr_sma is not None
            and latest_atr_sma > 0
            and latest_atr > latest_atr_sma * self._trend_atr_threshold
        ):
            # Price is clearly on one side of the SMA
            distance_pct = abs(latest_close - latest_sma) / latest_sma if latest_sma != 0 else 0.0
            if distance_pct > 0.0005:  # meaningful trend displacement for ZQ
                regime = MarketRegime.TREND
                bias = self._classify_macro_bias(bars, indicators)
                confidence = min(0.85, 0.55 + distance_pct * 100)
                direction_str = "above" if latest_close > latest_sma else "below"
                reason = (
                    f"Price ({latest_close:.4f}) {direction_str} SMA "
                    f"({latest_sma:.4f}) with elevated ATR "
                    f"({latest_atr:.6f} > {latest_atr_sma * self._trend_atr_threshold:.6f})"
                )
                log.info("regime_classified", regime=regime.value, reason=reason, bias=bias.value)
                state = RegimeState(
                    regime=regime,
                    bias=bias,
                    confidence=confidence,
                    reason=reason,
                    classified_at=now_utc(),
                    is_override=False,
                )
                self._regime_cache[product] = state
                return state

        # ── 4. Range regime (tight DCW) ──
        if latest_dcw is not None and latest_dcw < self._range_dcw_threshold:
            regime = MarketRegime.RANGE
            bias = self._classify_macro_bias(bars, indicators)
            confidence = min(0.80, 0.50 + (self._range_dcw_threshold - latest_dcw) * 50)
            reason = (
                f"DCW ({latest_dcw:.6f}) below range threshold "
                f"({self._range_dcw_threshold})"
            )
            log.info("regime_classified", regime=regime.value, reason=reason, bias=bias.value)
            state = RegimeState(
                regime=regime,
                bias=bias,
                confidence=confidence,
                reason=reason,
                classified_at=now_utc(),
                is_override=False,
            )
            self._regime_cache[product] = state
            return state

        # ── 5. Default → RANGE ──
        regime = MarketRegime.RANGE
        bias = self._classify_macro_bias(bars, indicators)
        reason = "Default classification (no clear regime signal)"
        log.info("regime_classified", regime=regime.value, reason=reason, bias=bias.value)
        state = RegimeState(
            regime=regime,
            bias=bias,
            confidence=0.50,
            reason=reason,
            classified_at=now_utc(),
            is_override=False,
        )
        self._regime_cache[product] = state
        return state

    async def update_regime(
        self,
        product: str,
        update: RegimeUpdateRequest,
    ) -> RegimeState:
        """Manually override the regime for *product*.

        Parameters
        ----------
        product:
            Product symbol.
        update:
            The manual override payload.

        Returns
        -------
        RegimeState
            The new (overridden) regime state.
        """
        state = RegimeState(
            regime=update.regime,
            bias=update.bias,
            confidence=update.confidence if update.confidence is not None else 1.0,
            reason=update.reason or "Manual override",
            classified_at=now_utc(),
            is_override=True,
        )
        self._regime_cache[product] = state
        logger.info(
            "regime_overridden",
            product=product,
            regime=state.regime.value,
            bias=state.bias.value,
            reason=state.reason,
        )
        return state

    async def get_regime(self, product: str) -> RegimeState | None:
        """Return the cached regime for *product*, or ``None``."""
        return self._regime_cache.get(product)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_event_active(self, events: list[MacroEvent]) -> bool:
        """Check whether any event falls within the event window."""
        current_time = now_utc()
        for event in events:
            if is_within_event_window(
                event_time=event.event_time,
                current_time=current_time,
                window_hours=self._event_window_hours,
            ):
                logger.debug(
                    "event_active",
                    event_name=event.name,
                    event_time=event.event_time.isoformat(),
                )
                return True
        return False

    def _classify_macro_bias(
        self,
        bars: list[OHLCVBar],
        indicators: dict[str, Any],
    ) -> MacroBias:
        """Infer macro bias from price action vs SMA.

        Fed funds futures: *price declining → rates rising → hawkish*,
        *price rising → rates falling → dovish*.
        """
        if len(bars) < 2:
            return MacroBias.NEUTRAL

        sma_series: list[float] = indicators.get("sma", [])
        latest_sma = self._last_valid(sma_series)
        latest_close = bars[-1].close

        if latest_sma is None:
            # Fallback: compare last 5 closes
            recent = [b.close for b in bars[-5:]]
            if len(recent) >= 2:
                if recent[-1] < recent[0]:
                    return MacroBias.HAWKISH  # price declining = rates rising
                elif recent[-1] > recent[0]:
                    return MacroBias.DOVISH   # price rising = rates falling
            return MacroBias.NEUTRAL

        # Price below SMA → declining → hawkish
        if latest_close < latest_sma:
            return MacroBias.HAWKISH
        elif latest_close > latest_sma:
            return MacroBias.DOVISH
        return MacroBias.NEUTRAL

    @staticmethod
    def _last_valid(series: list[float]) -> float | None:
        """Return the last non-NaN value in *series*, or ``None``."""
        for v in reversed(series):
            if v is not None and not (isinstance(v, float) and math.isnan(v)):
                return v
        return None
