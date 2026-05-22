"""CurveFlattener: Spread strategy expecting curve flattening (spread narrowing)."""
from typing import Optional

from app.contracts.indicators import IndicatorSet
from app.contracts.market_data import OHLCVSeries
from app.contracts.regime import RegimeState, MacroBias
from app.contracts.signals import SignalDirection, StrategySignal
from app.contracts.strategy import EntryExitPlan
from app.strategies.base import BaseStrategy


class CurveFlattener(BaseStrategy):
    name = "curve_flattener"
    display_name = "Curve Flattener"

    def evaluate(
        self,
        series: OHLCVSeries,
        indicators: IndicatorSet,
        regime: RegimeState,
        product_config: dict,
    ) -> Optional[StrategySignal]:
        disabled, reason = self.should_disable(series, indicators, regime)
        if disabled:
            return None

        close = series.bars[-1].close
        confidence = 0.0
        direction = SignalDirection.FLAT
        rationale_parts: list[str] = []
        tick_size_bp = product_config.get("spread_tick_size_bp", 0.5)

        # Flattener profits from spread NARROWING (becoming less positive / more negative)

        # EMA trend on spread: downtrend = flattening
        ema_short = indicators.ema.get(9)
        ema_long = indicators.ema.get(21)
        if ema_short and ema_long and ema_short.values and ema_long.values:
            if ema_short.values[-1] < ema_long.values[-1]:
                confidence += 0.25
                direction = SignalDirection.SHORT  # Short the spread = flattener
                rationale_parts.append("Spread EMA9 < EMA21 — flattening trend")

        # Donchian breakdown on spread
        if indicators.donchian and indicators.donchian.lower_band:
            dc_lower = indicators.donchian.lower_band[-1]
            if close <= dc_lower:
                confidence += 0.2
                direction = SignalDirection.SHORT
                rationale_parts.append("Spread at Donchian lower — breakdown flattening")

        # ATR expansion
        if indicators.atr and indicators.atr.values and len(indicators.atr.values) >= 5:
            atr_val = indicators.atr.values[-1]
            prev_atr = indicators.atr.values[-5]
            if prev_atr > 0 and atr_val > prev_atr * 1.2:
                confidence += 0.15
                rationale_parts.append("Spread ATR expanding — active curve movement")

        # Macro bias: hawkish = rates expected higher = flattener favored
        if regime.macro_bias == MacroBias.HAWKISH:
            confidence += 0.15
            rationale_parts.append("Hawkish macro bias supports flattening")

        # SMA resistance
        sma_20 = indicators.sma.get(20)
        if sma_20 and sma_20.values and close < sma_20.values[-1]:
            confidence += 0.1
            rationale_parts.append("Spread below SMA20")

        confidence = min(confidence, 1.0)
        if confidence < 0.5 or direction != SignalDirection.SHORT:
            return None

        atr_val = indicators.atr.values[-1] if indicators.atr and indicators.atr.values else tick_size_bp * 5
        entry = close
        stop = close + 2.0 * atr_val
        target = close - 3.0 * atr_val
        rr = abs(target - entry) / abs(entry - stop) if abs(entry - stop) > 0 else 0

        return StrategySignal(
            strategy_name=self.name,
            symbol=series.symbol,
            timeframe=series.timeframe,
            direction=SignalDirection.SHORT,
            strength=self._classify_strength(1.0 - confidence),
            confidence=round(confidence, 3),
            entry_price=round(entry, 4),
            stop_price=round(stop, 4),
            target_price=round(target, 4),
            risk_reward_ratio=round(rr, 2),
            rationale=" | ".join(rationale_parts),
            regime=regime.regime.value,
            macro_bias=regime.macro_bias.value,
        )

    def build_entry_exit_plan(
        self,
        signal: StrategySignal,
        series: OHLCVSeries,
        indicators: IndicatorSet,
        product_config: dict,
    ) -> Optional[EntryExitPlan]:
        if not signal.entry_price or not signal.stop_price or not signal.target_price:
            return None
        tick_size = product_config.get("spread_tick_size_bp", 0.5)
        risk_ticks = abs(signal.entry_price - signal.stop_price) / tick_size
        reward_ticks = abs(signal.target_price - signal.entry_price) / tick_size

        return EntryExitPlan(
            symbol=signal.symbol,
            strategy_name=self.name,
            direction=signal.direction.value,
            entry_price=signal.entry_price,
            stop_price=signal.stop_price,
            primary_target=signal.target_price,
            risk_ticks=round(risk_ticks, 2),
            reward_ticks=round(reward_ticks, 2),
            risk_reward_ratio=signal.risk_reward_ratio or 0,
            confidence=signal.confidence,
            rationale=signal.rationale,
        )
