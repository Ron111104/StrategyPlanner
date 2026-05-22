"""Multi-Timeframe (MTF) Analysis Engine.

Evaluates alignment across 1M, 5M, 15M, 1H, 4H, 1D timeframes.
Provides trend alignment, volatility alignment, structure alignment,
and composite MTF scoring for strategy and ladder adjustment.
"""
from typing import Optional

from app.contracts.indicators import IndicatorSet
from app.core.logging import get_logger
from app.services.cache import CacheManager
from app.services.indicator_engine import IndicatorEngine

logger = get_logger(__name__)

TIMEFRAME_ORDER = ["1M", "5M", "15M", "1H", "4H", "1D"]

TIMEFRAME_WEIGHT: dict[str, float] = {
    "1M": 0.05,
    "5M": 0.10,
    "15M": 0.15,
    "1H": 0.25,
    "4H": 0.25,
    "1D": 0.20,
}


class MTFAnalysis:
    """Result of multi-timeframe analysis for a symbol."""

    def __init__(self) -> None:
        self.symbol: str = ""
        self.anchor_tf: str = ""
        self.trend_alignment: float = 0.0
        self.volatility_alignment: float = 0.0
        self.structure_alignment: float = 0.0
        self.composite_score: float = 0.0
        self.direction_bias: str = "neutral"
        self.timeframe_scores: dict[str, dict[str, float]] = {}
        self.warnings: list[str] = []

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "anchor_tf": self.anchor_tf,
            "trend_alignment": round(self.trend_alignment, 3),
            "volatility_alignment": round(self.volatility_alignment, 3),
            "structure_alignment": round(self.structure_alignment, 3),
            "composite_score": round(self.composite_score, 3),
            "direction_bias": self.direction_bias,
            "timeframe_scores": self.timeframe_scores,
            "warnings": self.warnings,
        }


class MTFEngine:
    """Multi-timeframe analysis engine."""

    def __init__(self) -> None:
        self._cache = CacheManager()
        self._indicator_engine = IndicatorEngine()

    def analyze(self, symbol: str, anchor_tf: str) -> MTFAnalysis:
        """Run full MTF analysis for a symbol relative to an anchor timeframe."""
        result = MTFAnalysis()
        result.symbol = symbol
        result.anchor_tf = anchor_tf

        anchor_idx = TIMEFRAME_ORDER.index(anchor_tf) if anchor_tf in TIMEFRAME_ORDER else 3

        trend_scores: list[tuple[float, float]] = []
        vol_scores: list[tuple[float, float]] = []
        struct_scores: list[tuple[float, float]] = []

        for tf in TIMEFRAME_ORDER:
            weight = TIMEFRAME_WEIGHT.get(tf, 0.1)
            ind = self._cache.get_indicators(symbol, tf)

            tf_data: dict[str, float] = {"weight": weight}

            if not ind:
                tf_data["trend"] = 0.0
                tf_data["vol"] = 0.0
                tf_data["structure"] = 0.0
                result.timeframe_scores[tf] = tf_data
                continue

            # Trend score: EMA alignment
            t_score = self._score_trend(ind)
            tf_data["trend"] = round(t_score, 3)
            trend_scores.append((t_score, weight))

            # Volatility score: ATR relative position
            v_score = self._score_volatility(ind)
            tf_data["vol"] = round(v_score, 3)
            vol_scores.append((v_score, weight))

            # Structure score: compression/expansion
            s_score = self._score_structure(ind)
            tf_data["structure"] = round(s_score, 3)
            struct_scores.append((s_score, weight))

            result.timeframe_scores[tf] = tf_data

        # Compute weighted averages
        result.trend_alignment = self._weighted_avg(trend_scores)
        result.volatility_alignment = self._weighted_avg(vol_scores)
        result.structure_alignment = self._weighted_avg(struct_scores)

        # Composite = 50% trend + 25% vol + 25% structure
        result.composite_score = (
            result.trend_alignment * 0.50
            + result.volatility_alignment * 0.25
            + result.structure_alignment * 0.25
        )

        # Direction bias from trend alignment
        if result.trend_alignment > 0.2:
            result.direction_bias = "bullish"
        elif result.trend_alignment < -0.2:
            result.direction_bias = "bearish"
        else:
            result.direction_bias = "neutral"

        # Warnings
        if abs(result.trend_alignment) < 0.1:
            result.warnings.append("No clear trend alignment across timeframes")
        if result.volatility_alignment > 0.7:
            result.warnings.append("High volatility across multiple timeframes")

        return result

    def get_spacing_adjustment(self, mtf: MTFAnalysis) -> float:
        """Get ladder spacing adjustment factor from MTF analysis.

        Returns a multiplier: >1.0 = widen spacing, <1.0 = tighten.
        """
        # High vol alignment → widen spacing
        # High structure alignment (trending) → tighten spacing
        vol_adj = 1.0 + (mtf.volatility_alignment - 0.5) * 0.4
        struct_adj = 1.0 - (mtf.structure_alignment - 0.5) * 0.2
        return round(max(0.5, min(2.0, vol_adj * struct_adj)), 3)

    def get_confidence_adjustment(self, mtf: MTFAnalysis) -> float:
        """Get ladder confidence adjustment from MTF alignment.

        Returns adjustment: -0.2 to +0.2.
        """
        if abs(mtf.trend_alignment) > 0.5:
            return 0.15
        elif abs(mtf.trend_alignment) > 0.3:
            return 0.05
        elif abs(mtf.trend_alignment) < 0.1:
            return -0.1
        return 0.0

    def get_size_adjustment(self, mtf: MTFAnalysis) -> float:
        """Get position size adjustment from MTF analysis.

        Returns multiplier: 0.5 to 1.5.
        """
        score = mtf.composite_score
        if score > 0.6:
            return 1.2
        elif score > 0.4:
            return 1.0
        elif score > 0.2:
            return 0.8
        return 0.6

    # ---- Scoring helpers ----

    def _score_trend(self, ind: IndicatorSet) -> float:
        """Score trend direction: -1 (bearish) to +1 (bullish)."""
        signals: list[float] = []

        # EMA 9/21 alignment
        ema_s = ind.ema.get(9)
        ema_l = ind.ema.get(21)
        if ema_s and ema_l and ema_s.values and ema_l.values:
            diff = ema_s.values[-1] - ema_l.values[-1]
            avg = (abs(ema_s.values[-1]) + abs(ema_l.values[-1])) / 2
            if avg > 0:
                signals.append(max(-1.0, min(1.0, diff / avg * 100)))

        # SMA 20/50 alignment
        sma_s = ind.sma.get(20)
        sma_l = ind.sma.get(50)
        if sma_s and sma_l and sma_s.values and sma_l.values:
            diff = sma_s.values[-1] - sma_l.values[-1]
            avg = (abs(sma_s.values[-1]) + abs(sma_l.values[-1])) / 2
            if avg > 0:
                signals.append(max(-1.0, min(1.0, diff / avg * 100)))

        # RSI direction
        if ind.rsi and ind.rsi.values:
            rsi = ind.rsi.values[-1]
            signals.append((rsi - 50) / 50)

        # MACD histogram
        if ind.macd and ind.macd.histogram:
            hist = ind.macd.histogram[-1]
            signals.append(max(-1.0, min(1.0, hist * 10)))

        if not signals:
            return 0.0
        return sum(signals) / len(signals)

    def _score_volatility(self, ind: IndicatorSet) -> float:
        """Score volatility level: 0 (low) to 1 (extreme)."""
        if ind.atr and ind.atr.values and len(ind.atr.values) >= 20:
            vals = ind.atr.values
            current = vals[-1]
            lookback = vals[-50:] if len(vals) >= 50 else vals
            rank = sum(1 for v in lookback if v <= current)
            return rank / len(lookback)
        return 0.5

    def _score_structure(self, ind: IndicatorSet) -> float:
        """Score structural clarity: 0 (choppy) to 1 (clear trend/structure)."""
        signals: list[float] = []

        # Range compression → high value = compressed (range-bound)
        if ind.range_compression and ind.range_compression.values:
            rc = ind.range_compression.values[-1]
            signals.append(1.0 - min(1.0, rc))

        # Donchian breakout proximity
        if ind.donchian and ind.donchian.upper_band and ind.donchian.lower_band:
            upper = ind.donchian.upper_band[-1]
            lower = ind.donchian.lower_band[-1]
            rng = upper - lower
            if rng > 0 and ind.donchian.values:
                mid = ind.donchian.values[-1]
                # Score how close price is to a boundary
                signals.append(min(1.0, abs(mid - (upper + lower) / 2) / rng * 2))

        if not signals:
            return 0.5
        return sum(signals) / len(signals)

    @staticmethod
    def _weighted_avg(items: list[tuple[float, float]]) -> float:
        if not items:
            return 0.0
        total_w = sum(w for _, w in items)
        if total_w <= 0:
            return 0.0
        return sum(v * w for v, w in items) / total_w
