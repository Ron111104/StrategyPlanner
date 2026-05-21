"""Tests for the RegimeEngine."""

import pytest
from datetime import datetime, timedelta, timezone

from app.contracts.macro_inputs import MacroBias, MacroEvent, MarketRegime, RegimeUpdateRequest
from app.services.regime_engine import RegimeEngine


class TestRegimeEngine:
    @pytest.mark.asyncio
    async def test_classify_range_regime(self, regime_engine, sample_bars, indicator_engine):
        """Default classification should be range for stable data."""
        indicators = indicator_engine.compute_all(sample_bars, indicator_engine._config)
        regime = await regime_engine.classify_regime(
            product="FFN25",
            bars=sample_bars,
            indicators=indicators,
        )
        assert regime.current_regime in [MarketRegime.RANGE, MarketRegime.TREND, MarketRegime.VOLATILITY]
        assert regime.confidence > 0

    @pytest.mark.asyncio
    async def test_classify_event_regime(self, regime_engine, sample_bars, indicator_engine):
        """Should classify as event when active events present."""
        indicators = indicator_engine.compute_all(sample_bars, indicator_engine._config)
        events = [
            MacroEvent(
                event_name="FOMC",
                event_time=datetime.now(timezone.utc) + timedelta(hours=1),
                impact="high",
                description="Rate decision",
            )
        ]
        regime = await regime_engine.classify_regime(
            product="FFN25",
            bars=sample_bars,
            indicators=indicators,
            events=events,
        )
        assert regime.current_regime == MarketRegime.EVENT

    @pytest.mark.asyncio
    async def test_regime_priority_order(self, regime_engine, sample_bars, indicator_engine):
        """Event should override all other regime classifications."""
        indicators = indicator_engine.compute_all(sample_bars, indicator_engine._config)
        events = [
            MacroEvent(
                event_name="CPI",
                event_time=datetime.now(timezone.utc),
                impact="high",
                description="CPI release",
            )
        ]
        regime = await regime_engine.classify_regime(
            product="FFN25", bars=sample_bars, indicators=indicators, events=events
        )
        # Event should be highest priority
        assert regime.current_regime == MarketRegime.EVENT

    @pytest.mark.asyncio
    async def test_manual_override(self, regime_engine):
        """Manual override should set regime directly."""
        update = RegimeUpdateRequest(
            regime=MarketRegime.TREND,
            bias=MacroBias.HAWKISH,
            manual_override=True,
        )
        regime = await regime_engine.update_regime("FFN25", update)
        assert regime.current_regime == MarketRegime.TREND
        assert regime.macro_bias == MacroBias.HAWKISH
        assert regime.source == "manual"

    @pytest.mark.asyncio
    async def test_macro_bias_classification(self, regime_engine, sample_bars, indicator_engine):
        """Macro bias should be classified as hawkish, dovish, or neutral."""
        indicators = indicator_engine.compute_all(sample_bars, indicator_engine._config)
        regime = await regime_engine.classify_regime(
            product="FFN25", bars=sample_bars, indicators=indicators
        )
        assert regime.macro_bias in [MacroBias.HAWKISH, MacroBias.DOVISH, MacroBias.NEUTRAL]

    @pytest.mark.asyncio
    async def test_regime_caching(self, regime_engine, sample_bars, indicator_engine):
        """Classified regime should be cached."""
        indicators = indicator_engine.compute_all(sample_bars, indicator_engine._config)
        await regime_engine.classify_regime("FFN25", sample_bars, indicators)
        cached = await regime_engine.get_regime("FFN25")
        assert cached is not None
        assert cached.current_regime is not None
