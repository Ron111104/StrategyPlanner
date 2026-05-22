"""TrendFedRepricing: Trend-following strategy for Fed repricing moves."""
from typing import Optional

from app.contracts.indicators import IndicatorSet
from app.contracts.market_data import OHLCVSeries
from app.contracts.regime import RegimeState, RegimeType, MacroBias
from app.contracts.signals import SignalDirection, SignalStrength, StrategySignal
from app.contracts.strategy import EntryExitPlan
from app.strategies.base import BaseStrategy


class TrendFedRepricing(BaseStrategy):
    name = "trend_fed_repricing"
    display_name = "Trend Fed Repricing"

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

        # EMA alignment check
        ema_short = indicators.ema.get(9)
        ema_long = indicators.ema.get(21)
        if ema_short and ema_long and ema_short.values and ema_long.values:
            short_val = ema_short.values[-1]
            long_val = ema_long.values[-1]

            if short_val > long_val:
                confidence += 0.3
                direction = SignalDirection.LONG
                rationale_parts.append("EMA9 > EMA21 — bullish alignment")
            elif short_val < long_val:
                confidence += 0.3
                direction = SignalDirection.SHORT
                rationale_parts.append("EMA9 < EMA21 — bearish alignment")

        # ATR expansion confirms trend
        if indicators.atr and indicators.atr.values and len(indicators.atr.values) >= 5:
            recent_atr = indicators.atr.values[-1]
            prev_atr = indicators.atr.values[-5]
            if prev_atr > 0 and recent_atr > prev_atr * 1.2:
                confidence += 0.2
                rationale_parts.append("ATR expanding — trend acceleration")

        # Donchian breakout
        if indicators.donchian and indicators.donchian.upper_band and indicators.donchian.lower_band:
            dc_upper = indicators.donchian.upper_band[-1]
            dc_lower = indicators.donchian.lower_band[-1]
            if close >= dc_upper and direction == SignalDirection.LONG:
                confidence += 0.2
                rationale_parts.append("Price at Donchian upper — breakout")
            elif close <= dc_lower and direction == SignalDirection.SHORT:
                confidence += 0.2
                rationale_parts.append("Price at Donchian lower — breakdown")

        # Macro bias alignment
        if regime.macro_bias == MacroBias.DOVISH and direction == SignalDirection.LONG:
            confidence += 0.15
            rationale_parts.append("Dovish bias supports long rates (higher price)")
        elif regime.macro_bias == MacroBias.HAWKISH and direction == SignalDirection.SHORT:
            confidence += 0.15
            rationale_parts.append("Hawkish bias supports short rates (lower price)")

        confidence = min(confidence, 1.0)
        if confidence < 0.5 or direction == SignalDirection.FLAT:
            return None

        tick_size = product_config.get("outright_tick_size", 0.005)
        atr_val = indicators.atr.values[-1] if indicators.atr and indicators.atr.values else tick_size * 10

        if direction == SignalDirection.LONG:
            entry = close
            stop = close - 2.0 * atr_val
            target = close + 3.0 * atr_val
        else:
            entry = close
            stop = close + 2.0 * atr_val
            target = close - 3.0 * atr_val

        rr = abs(target - entry) / abs(entry - stop) if abs(entry - stop) > 0 else 0

        return StrategySignal(
            strategy_name=self.name,
            symbol=series.symbol,
            timeframe=series.timeframe,
            direction=direction,
            strength=self._classify_strength(confidence),
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

        tick_size = product_config.get("outright_tick_size", 0.005)
        risk_ticks = abs(signal.entry_price - signal.stop_price) / tick_size
        reward_ticks = abs(signal.target_price - signal.entry_price) / tick_size

        secondary = None
        tertiary = None
        atr_val = indicators.atr.values[-1] if indicators.atr and indicators.atr.values else tick_size * 10

        if signal.direction == SignalDirection.LONG:
            secondary = round(signal.entry_price + 4.0 * atr_val, 4)
            tertiary = round(signal.entry_price + 5.0 * atr_val, 4)
        elif signal.direction == SignalDirection.SHORT:
            secondary = round(signal.entry_price - 4.0 * atr_val, 4)
            tertiary = round(signal.entry_price - 5.0 * atr_val, 4)

        return EntryExitPlan(
            symbol=signal.symbol,
            strategy_name=self.name,
            direction=signal.direction.value,
            entry_price=signal.entry_price,
            stop_price=signal.stop_price,
            primary_target=signal.target_price,
            secondary_target=secondary,
            tertiary_target=tertiary,
            risk_ticks=round(risk_ticks, 2),
            reward_ticks=round(reward_ticks, 2),
            risk_reward_ratio=signal.risk_reward_ratio or 0,
            confidence=signal.confidence,
            rationale=signal.rationale,
        )
