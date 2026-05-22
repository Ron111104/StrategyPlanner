"""VolatilityFade: Fade extreme volatility expansions expecting contraction."""
from typing import Optional

from app.contracts.indicators import IndicatorSet
from app.contracts.market_data import OHLCVSeries
from app.contracts.regime import RegimeState
from app.contracts.signals import SignalDirection, StrategySignal
from app.contracts.strategy import EntryExitPlan
from app.strategies.base import BaseStrategy


class VolatilityFade(BaseStrategy):
    name = "volatility_fade"
    display_name = "Volatility Fade"

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

        # ATR at extreme levels
        if not indicators.atr or not indicators.atr.values or len(indicators.atr.values) < 20:
            return None

        atr_values = indicators.atr.values
        atr_val = atr_values[-1]
        sorted_atr = sorted(atr_values[-100:] if len(atr_values) >= 100 else atr_values)
        rank = sum(1 for v in sorted_atr if v <= atr_val)
        vol_pct = rank / len(sorted_atr) * 100

        if vol_pct > 85:
            confidence += 0.3
            rationale_parts.append(f"ATR at {vol_pct:.0f}th percentile — extreme volatility")
        elif vol_pct > 70:
            confidence += 0.15
            rationale_parts.append(f"ATR at {vol_pct:.0f}th percentile — elevated volatility")
        else:
            return None

        # DCW expansion confirmation
        if indicators.dcw and indicators.dcw.values and len(indicators.dcw.values) >= 10:
            recent_dcw = indicators.dcw.values[-1]
            avg_dcw = sum(indicators.dcw.values[-20:]) / min(len(indicators.dcw.values), 20)
            if avg_dcw > 0 and recent_dcw / avg_dcw > 1.5:
                confidence += 0.15
                rationale_parts.append("DCW expanded — volatility spike confirmed")

        # Direction: fade toward Bollinger midline
        if indicators.bollinger and indicators.bollinger.middle_band and indicators.bollinger.upper_band:
            bb_mid = indicators.bollinger.middle_band[-1]
            bb_upper = indicators.bollinger.upper_band[-1]
            bb_lower = indicators.bollinger.lower_band[-1] if indicators.bollinger.lower_band else bb_mid

            if close > bb_mid:
                direction = SignalDirection.SHORT
                confidence += 0.2
                rationale_parts.append("Price above Bollinger mid — fade toward mean")
            elif close < bb_mid:
                direction = SignalDirection.LONG
                confidence += 0.2
                rationale_parts.append("Price below Bollinger mid — fade toward mean")
        else:
            # Fallback: fade recent bar direction
            if series.length >= 2:
                if series.bars[-1].close > series.bars[-2].close:
                    direction = SignalDirection.SHORT
                    confidence += 0.1
                else:
                    direction = SignalDirection.LONG
                    confidence += 0.1

        confidence = min(confidence, 1.0)
        if confidence < 0.45 or direction == SignalDirection.FLAT:
            return None

        if direction == SignalDirection.LONG:
            entry = close
            stop = close - 2.0 * atr_val
            target = close + 1.5 * atr_val
        else:
            entry = close
            stop = close + 2.0 * atr_val
            target = close - 1.5 * atr_val

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
        if indicators.bollinger and indicators.bollinger.middle_band:
            secondary = round(indicators.bollinger.middle_band[-1], 4)

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
