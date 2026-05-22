"""MeanReversionRange: Mean-reversion strategy for range-bound markets."""
from typing import Optional

from app.contracts.indicators import IndicatorSet
from app.contracts.market_data import OHLCVSeries
from app.contracts.regime import RegimeState
from app.contracts.signals import SignalDirection, StrategySignal
from app.contracts.strategy import EntryExitPlan
from app.strategies.base import BaseStrategy


class MeanReversionRange(BaseStrategy):
    name = "mean_reversion_range"
    display_name = "Mean Reversion Range"

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

        # Bollinger band mean reversion
        if indicators.bollinger and indicators.bollinger.upper_band and indicators.bollinger.lower_band:
            bb_upper = indicators.bollinger.upper_band[-1]
            bb_lower = indicators.bollinger.lower_band[-1]
            bb_mid = indicators.bollinger.values[-1] if indicators.bollinger.values else (bb_upper + bb_lower) / 2

            bb_width = bb_upper - bb_lower
            if bb_width > 0:
                position = (close - bb_lower) / bb_width

                if position > 0.95:
                    direction = SignalDirection.SHORT
                    confidence += 0.4
                    rationale_parts.append(f"Price at upper Bollinger ({position:.1%}) — overbought")
                elif position < 0.05:
                    direction = SignalDirection.LONG
                    confidence += 0.4
                    rationale_parts.append(f"Price at lower Bollinger ({position:.1%}) — oversold")
                elif position > 0.8:
                    direction = SignalDirection.SHORT
                    confidence += 0.25
                    rationale_parts.append(f"Price near upper Bollinger ({position:.1%})")
                elif position < 0.2:
                    direction = SignalDirection.LONG
                    confidence += 0.25
                    rationale_parts.append(f"Price near lower Bollinger ({position:.1%})")

        # SMA reversion
        sma_20 = indicators.sma.get(20)
        if sma_20 and sma_20.values:
            sma_val = sma_20.values[-1]
            deviation = (close - sma_val) / sma_val if sma_val != 0 else 0

            if abs(deviation) > 0.002:
                if deviation > 0 and direction in (SignalDirection.SHORT, SignalDirection.FLAT):
                    confidence += 0.15
                    direction = SignalDirection.SHORT
                    rationale_parts.append(f"Price above SMA20 by {deviation:.3%} — revert to mean")
                elif deviation < 0 and direction in (SignalDirection.LONG, SignalDirection.FLAT):
                    confidence += 0.15
                    direction = SignalDirection.LONG
                    rationale_parts.append(f"Price below SMA20 by {abs(deviation):.3%} — revert to mean")

        # DCW compression confirms range
        if indicators.dcw and indicators.dcw.values and len(indicators.dcw.values) >= 10:
            recent_dcw = indicators.dcw.values[-1]
            avg_dcw = sum(indicators.dcw.values[-20:]) / min(len(indicators.dcw.values), 20)
            if avg_dcw > 0 and recent_dcw / avg_dcw < 0.7:
                confidence += 0.2
                rationale_parts.append("DCW compressed — range environment confirmed")

        confidence = min(confidence, 1.0)
        if confidence < 0.4 or direction == SignalDirection.FLAT:
            return None

        atr_val = indicators.atr.values[-1] if indicators.atr and indicators.atr.values else tick_size * 8

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

        # Mean reversion targets: SMA as secondary
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
