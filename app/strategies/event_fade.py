"""EventFade: Fade the initial event reaction for mean-reversion post-event."""
from typing import Optional

from app.contracts.indicators import IndicatorSet
from app.contracts.market_data import OHLCVSeries
from app.contracts.regime import RegimeState, MacroBias
from app.contracts.signals import SignalDirection, StrategySignal
from app.contracts.strategy import EntryExitPlan
from app.strategies.base import BaseStrategy


class EventFade(BaseStrategy):
    name = "event_fade"
    display_name = "Event Fade"

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
        tick_size = product_config.get("outright_tick_size", 0.005)

        if not indicators.atr or not indicators.atr.values:
            return None

        atr_val = indicators.atr.values[-1]

        # Detect overextension from recent bars (spike + reversal candle)
        if series.length >= 5:
            recent_bars = series.bars[-5:]
            max_high = max(b.high for b in recent_bars)
            min_low = min(b.low for b in recent_bars)
            total_range = max_high - min_low

            if atr_val > 0 and total_range > 3.0 * atr_val:
                # Large event move detected
                last_bar = series.bars[-1]
                prev_bar = series.bars[-2]

                # Check for reversal candle
                if last_bar.close < last_bar.open and prev_bar.close > prev_bar.open:
                    # Bearish reversal after bullish spike → fade long
                    direction = SignalDirection.SHORT
                    confidence += 0.35
                    rationale_parts.append("Bearish reversal candle after event spike")
                elif last_bar.close > last_bar.open and prev_bar.close < prev_bar.open:
                    # Bullish reversal after bearish spike → fade short
                    direction = SignalDirection.LONG
                    confidence += 0.35
                    rationale_parts.append("Bullish reversal candle after event drop")

        # Bollinger band overextension
        if indicators.bollinger and indicators.bollinger.upper_band and indicators.bollinger.lower_band:
            bb_upper = indicators.bollinger.upper_band[-1]
            bb_lower = indicators.bollinger.lower_band[-1]
            bb_width = bb_upper - bb_lower

            if bb_width > 0:
                position = (close - bb_lower) / bb_width
                if position > 0.9 and direction in (SignalDirection.SHORT, SignalDirection.FLAT):
                    confidence += 0.2
                    if direction == SignalDirection.FLAT:
                        direction = SignalDirection.SHORT
                    rationale_parts.append(f"Extreme upper Bollinger position ({position:.1%})")
                elif position < 0.1 and direction in (SignalDirection.LONG, SignalDirection.FLAT):
                    confidence += 0.2
                    if direction == SignalDirection.FLAT:
                        direction = SignalDirection.LONG
                    rationale_parts.append(f"Extreme lower Bollinger position ({position:.1%})")

        # SMA distance — mean reversion target
        sma_20 = indicators.sma.get(20)
        if sma_20 and sma_20.values:
            sma_val = sma_20.values[-1]
            deviation = abs(close - sma_val) / sma_val if sma_val > 0 else 0
            if deviation > 0.003:
                confidence += 0.15
                rationale_parts.append(f"Price deviated {deviation:.3%} from SMA20")

        confidence = min(confidence, 1.0)
        if confidence < 0.5 or direction == SignalDirection.FLAT:
            return None

        if direction == SignalDirection.LONG:
            entry = close
            stop = close - 1.5 * atr_val
            target = close + 2.0 * atr_val
        else:
            entry = close
            stop = close + 1.5 * atr_val
            target = close - 2.0 * atr_val

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
        sma_20 = indicators.sma.get(20)
        if sma_20 and sma_20.values:
            secondary = round(sma_20.values[-1], 4)

        return EntryExitPlan(
            symbol=signal.symbol,
            strategy_name=self.name,
            direction=signal.direction.value,
            entry_price=signal.entry_price,
            stop_price=signal.stop_price,
            primary_target=signal.target_price,
            secondary_target=secondary,
            risk_ticks=round(risk_ticks, 2),
            reward_ticks=round(reward_ticks, 2),
            risk_reward_ratio=signal.risk_reward_ratio or 0,
            confidence=signal.confidence,
            rationale=signal.rationale,
        )
