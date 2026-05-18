"""
Regime Engine — market regime classification and management.

Priority: event → volatility → trend → range → no_signal
Supports manual override, event lock windows, and expiration.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.contracts.macro_inputs import (
    MacroBias,
    MacroEvent,
    MarketRegime,
    RegimeClassificationInput,
    RegimeState,
    RegimeUpdateRequest,
)
from app.core.logging import get_logger
from app.utils.datetime_helpers import is_within_event_window, utc_now

logger = get_logger(__name__)


class RegimeEngine:
    """
    Institutional regime classification engine.

    Classifies current market regime using rule-based logic,
    supports manual overrides, event locks, and expiration.
    """

    def __init__(self, settings: dict[str, Any]) -> None:
        regime_cfg = settings.get("regime", {})
        vol_cfg = settings.get("volatility", {})

        self._trend_threshold: float = regime_cfg.get("trend_ma_separation_threshold", 0.010)
        self._range_atr_pct: float = regime_cfg.get("range_atr_percentile_threshold", 30)
        self._vol_atr_mult: float = regime_cfg.get("volatility_atr_multiplier", 1.5)
        self._event_lock_hours: float = regime_cfg.get("event_lock_window_hours", 4)
        self._regime_expiry_hours: float = regime_cfg.get("regime_expiration_hours", 24)

        self._low_vol: float = vol_cfg.get("low_vol_threshold", 0.8)
        self._high_vol: float = vol_cfg.get("high_vol_threshold", 1.8)

        # State
        self._current_state: RegimeState = RegimeState()
        self._events: list[MacroEvent] = []

        logger.info("regime_engine_initialized")

    @property
    def current_state(self) -> RegimeState:
        return self._check_expiration(self._current_state)

    def classify(self, input_data: RegimeClassificationInput) -> RegimeState:
        """
        Rule-based regime classification.

        Priority: event → volatility → trend → range → no_signal
        """
        now = utc_now()

        # Check manual override first
        if self._current_state.is_manual_override:
            state = self._check_expiration(self._current_state)
            if state.is_manual_override:
                return state

        # 1. EVENT regime — highest priority
        active_events = self._get_active_events(now)
        if active_events:
            event_lock = any(
                is_within_event_window(e.scheduled_time, e.lock_window_hours)
                for e in active_events
            )
            state = RegimeState(
                regime=MarketRegime.EVENT,
                macro_bias=self._current_state.macro_bias,
                confidence=0.9,
                active_events=active_events,
                event_lock_active=event_lock,
                volatility_level=input_data.current_atr,
                classified_at=now,
                classification_reason="Active macro events detected",
            )
            self._current_state = state
            return state

        # 2. VOLATILITY regime
        if input_data.atr_percentile > 80 or input_data.current_atr > self._high_vol:
            state = RegimeState(
                regime=MarketRegime.VOLATILITY,
                macro_bias=self._current_state.macro_bias,
                confidence=round(min(input_data.atr_percentile / 100, 0.95), 2),
                volatility_level=input_data.current_atr,
                classified_at=now,
                classification_reason=f"High volatility: ATR pctl={input_data.atr_percentile:.0f}%",
            )
            self._current_state = state
            return state

        # 3. TREND regime
        ma_separation = abs(input_data.ma_fast - input_data.ma_slow) / input_data.price
        if ma_separation > self._trend_threshold:
            direction = "bullish" if input_data.ma_fast > input_data.ma_slow else "bearish"
            state = RegimeState(
                regime=MarketRegime.TREND,
                macro_bias=self._current_state.macro_bias,
                confidence=round(min(ma_separation / (self._trend_threshold * 3), 0.9), 2),
                volatility_level=input_data.current_atr,
                classified_at=now,
                classification_reason=f"Trend detected: {direction}, MA sep={ma_separation:.4f}",
            )
            self._current_state = state
            return state

        # 4. RANGE regime
        if input_data.atr_percentile < self._range_atr_pct:
            state = RegimeState(
                regime=MarketRegime.RANGE,
                macro_bias=self._current_state.macro_bias,
                confidence=round(1.0 - (input_data.atr_percentile / 100), 2),
                volatility_level=input_data.current_atr,
                classified_at=now,
                classification_reason=f"Range: low ATR pctl={input_data.atr_percentile:.0f}%",
            )
            self._current_state = state
            return state

        # 5. NO SIGNAL — default
        state = RegimeState(
            regime=MarketRegime.NO_SIGNAL,
            macro_bias=self._current_state.macro_bias,
            volatility_level=input_data.current_atr,
            classified_at=now,
            classification_reason="No clear regime classification",
        )
        self._current_state = state
        return state

    def update(self, request: RegimeUpdateRequest) -> RegimeState:
        """Apply a manual regime update/override."""
        now = utc_now()

        if request.regime is not None:
            self._current_state.regime = request.regime
            self._current_state.is_manual_override = True
            if request.override_expiration_hours:
                self._current_state.override_expiration = now + timedelta(
                    hours=request.override_expiration_hours
                )

        if request.macro_bias is not None:
            self._current_state.macro_bias = request.macro_bias

        if request.active_events is not None:
            self._events = request.active_events
            self._current_state.active_events = request.active_events

        if request.force_event_lock is not None:
            self._current_state.event_lock_active = request.force_event_lock
            if request.force_event_lock:
                self._current_state.event_lock_expiration = now + timedelta(
                    hours=self._event_lock_hours
                )

        if request.volatility_override is not None:
            self._current_state.volatility_level = request.volatility_override

        self._current_state.classified_at = now
        self._current_state.classification_reason = "Manual override applied"

        logger.info(
            "regime_updated",
            regime=self._current_state.regime.value,
            bias=self._current_state.macro_bias.value,
            manual=self._current_state.is_manual_override,
        )

        return self._current_state

    def add_event(self, event: MacroEvent) -> None:
        """Add a scheduled macro event."""
        self._events.append(event)
        logger.info("macro_event_added", event=event.name, time=str(event.scheduled_time))

    def clear_events(self) -> None:
        """Clear all scheduled events."""
        self._events.clear()
        self._current_state.active_events.clear()
        self._current_state.event_lock_active = False

    def _get_active_events(self, now: datetime) -> list[MacroEvent]:
        """Get events within their lock window."""
        return [
            e for e in self._events
            if is_within_event_window(e.scheduled_time, e.lock_window_hours)
        ]

    def _check_expiration(self, state: RegimeState) -> RegimeState:
        """Check and handle regime/event lock expiration."""
        now = utc_now()

        if state.is_manual_override and state.override_expiration:
            if now > state.override_expiration.replace(tzinfo=timezone.utc) if state.override_expiration.tzinfo is None else now > state.override_expiration:
                state.is_manual_override = False
                state.override_expiration = None
                state.classification_reason = "Manual override expired"
                logger.info("regime_override_expired")

        if state.event_lock_active and state.event_lock_expiration:
            exp = state.event_lock_expiration.replace(tzinfo=timezone.utc) if state.event_lock_expiration.tzinfo is None else state.event_lock_expiration
            if now > exp:
                state.event_lock_active = False
                state.event_lock_expiration = None
                logger.info("event_lock_expired")

        return state
