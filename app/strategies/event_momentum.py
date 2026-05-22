"""EventMomentum: Momentum strategy around macro events (FOMC, NFP, CPI)."""
from typing import Optional

from app.contracts.indicators import IndicatorSet
from app.contracts.market_data import OHLCVSeries
from app.contracts.regime import RegimeState, RegimeType, MacroBias
from app.contracts.signals import SignalDirection, StrategySignal
from app.contracts.strategy import EntryExitPlan
from app.strategies.base import BaseStrategy


class EventMomentum(BaseStrategy):
    name = "event_momentum"
    display_name = "Event Momentum"

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
        prev_close = series.bars[-2].close if series.length >= 2 else close
        confidence = 0.0
        direction = SignalDirection.FLAT
        rationale_parts: list[str] = []
        tick_size = product_config.get("outright_tick_size", 0.005)

        # Large move detection
        if indicators.atr and indicators.atr.values:
            atr_val = indicators.atr.values[-1]
            move = close - prev_close

            if atr_val > 0:
                move_multiple = abs(move) / atr_val
                if move_multiple > 2.0:
                    confidence += 0.35
                    if move > 0:
                        direction = SignalDirection.LONG
                        rationale_parts.append(f"Large bullish move: {move_multiple:.1f}x ATR")
                    else:
                        direction = SignalDirection.SHORT
                        rationale_parts.append(f"Large bearish move: {move_multiple:.1f}x ATR")
                elif move_multiple > 1.5:
                    confidence += 0.2
                    if move > 0:
                        direction = SignalDirection.LONG
                    else:
                        direction = SignalDirection.SHORT
                    rationale_parts.append(f"Significant move: {move_multiple:.1f}x ATR")

        # Volume surge (if available)
        if series.length >= 10:
            recent_vol = series.bars[-1].volume
            avg_vol = sum(b.volume for b in series.bars[-10:]) / 10
            if avg_vol > 0 and recent_vol > avg_vol * 2.0:
                confidence += 0.15
                rationale_parts.append(f"Volume surge: {recent_vol/avg_vol:.1f}x average")

        # Momentum continuation: Donchian breakout
        if indicators.donchian and indicators.donchian.upper_band and indicators.donchian.lower_band:
            dc_upper = indicators.donchian.upper_band[-1]
            dc_lower = indicators.donchian.lower_band[-1]
            if close > dc_upper and direction == SignalDirection.LONG:
                confidence += 0.2
                rationale_parts.append("Donchian breakout confirms momentum")
            elif close < dc_lower and direction == SignalDirection.SHORT:
                confidence += 0.2
                rationale_parts.append("Donchian breakdown confirms momentum")

        # Macro bias alignment
        if regime.macro_bias == MacroBias.DOVISH and direction == SignalDirection.LONG:
            confidence += 0.1
            rationale_parts.append("Dovish macro aligns with long")
        elif regime.macro_bias == MacroBias.HAWKISH and direction == SignalDirection.SHORT:
            confidence += 0.1
            rationale_parts.append("Hawkish macro aligns with short")

        confidence = min(confidence, 1.0)
        if confidence < 0.5 or direction == SignalDirection.FLAT:
            return None

        atr_val = indicators.atr.values[-1] if indicators.atr and indicators.atr.values else tick_size * 10
        if direction == SignalDirection.LONG:
            entry = close
            stop = close - 1.0 * atr_val
            target = close + 2.5 * atr_val
        else:
            entry = close
            stop = close + 1.0 * atr_val
            target = close - 2.5 * atr_val

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
