"""
Indicator Engine — institutional-grade technical indicator computation.

Implements all indicators with Wilder smoothing, caching, and incremental recalculation.
MANDATORY: ATR (Wilder), SMA, EMA, Donchian Channels, Bollinger Bands, DCW.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from app.contracts.market_data import OHLCVBar, SpreadBar
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class IndicatorResult:
    """Complete indicator computation result for a bar series."""
    product: str
    bar_count: int
    atr: list[float] = field(default_factory=list)
    current_atr: float = 0.0
    sma_fast: list[float] = field(default_factory=list)
    sma_slow: list[float] = field(default_factory=list)
    ema_fast: list[float] = field(default_factory=list)
    ema_slow: list[float] = field(default_factory=list)
    donchian_upper: list[float] = field(default_factory=list)
    donchian_lower: list[float] = field(default_factory=list)
    donchian_mid: list[float] = field(default_factory=list)
    current_donchian_upper: float = 0.0
    current_donchian_lower: float = 0.0
    bollinger_upper: list[float] = field(default_factory=list)
    bollinger_lower: list[float] = field(default_factory=list)
    bollinger_mid: list[float] = field(default_factory=list)
    dcw: list[float] = field(default_factory=list)
    current_dcw: float = 0.0
    spread_sma: list[float] = field(default_factory=list)
    spread_delta: list[float] = field(default_factory=list)
    atr_percentile: float = 0.0
    is_valid: bool = False
    insufficient_bars: bool = False
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "product": self.product, "bar_count": self.bar_count,
            "current_atr": self.current_atr, "atr_percentile": self.atr_percentile,
            "current_donchian_upper": self.current_donchian_upper,
            "current_donchian_lower": self.current_donchian_lower,
            "current_dcw": self.current_dcw, "is_valid": self.is_valid,
            "sma_fast_last": self.sma_fast[-1] if self.sma_fast else None,
            "sma_slow_last": self.sma_slow[-1] if self.sma_slow else None,
            "ema_fast_last": self.ema_fast[-1] if self.ema_fast else None,
            "ema_slow_last": self.ema_slow[-1] if self.ema_slow else None,
            "bollinger_upper_last": self.bollinger_upper[-1] if self.bollinger_upper else None,
            "bollinger_lower_last": self.bollinger_lower[-1] if self.bollinger_lower else None,
            "spread_sma_last": self.spread_sma[-1] if self.spread_sma else None,
            "spread_delta_last": self.spread_delta[-1] if self.spread_delta else None,
        }


class IndicatorEngine:
    """
    Institutional indicator engine with caching and validation.
    Computes all indicators from raw OHLCV bars.
    """

    def __init__(self, settings: dict[str, Any]) -> None:
        ind = settings.get("indicators", {})
        self._atr_length: int = ind.get("atr_length", 14)
        self._ma_fast: int = ind.get("ma_fast", 10)
        self._ma_slow: int = ind.get("ma_slow", 50)
        self._donchian_length: int = ind.get("donchian_length", 20)
        self._bollinger_length: int = ind.get("bollinger_length", 20)
        self._bollinger_std: float = ind.get("bollinger_std", 2.0)
        self._dcw_length: int = ind.get("dcw_length", 20)
        self._spread_sma_length: int = ind.get("spread_sma_length", 20)
        self._min_bars: int = ind.get("min_bars_required", 51)
        self._cache: dict[str, IndicatorResult] = {}
        logger.info("indicator_engine_initialized", atr_length=self._atr_length)

    def compute(self, bars: list[OHLCVBar], product: str, use_cache: bool = True) -> IndicatorResult:
        """Compute all indicators for an outright bar series."""
        cache_key = self._cache_key(product, bars)
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        result = IndicatorResult(product=product, bar_count=len(bars))
        if len(bars) < self._min_bars:
            result.insufficient_bars = True
            result.error = f"Insufficient bars: {len(bars)} < {self._min_bars}"
            return result

        try:
            closes = np.array([b.close for b in bars], dtype=np.float64)
            highs = np.array([b.high for b in bars], dtype=np.float64)
            lows = np.array([b.low for b in bars], dtype=np.float64)

            result.atr = self._compute_atr(highs, lows, closes)
            result.current_atr = result.atr[-1] if result.atr else 0.0

            result.sma_fast = self._compute_sma(closes, self._ma_fast)
            result.sma_slow = self._compute_sma(closes, self._ma_slow)
            result.ema_fast = self._compute_ema(closes, self._ma_fast)
            result.ema_slow = self._compute_ema(closes, self._ma_slow)

            dc_u, dc_l, dc_m = self._compute_donchian(highs, lows)
            result.donchian_upper, result.donchian_lower, result.donchian_mid = dc_u, dc_l, dc_m
            result.current_donchian_upper = dc_u[-1] if dc_u else 0.0
            result.current_donchian_lower = dc_l[-1] if dc_l else 0.0

            bb_u, bb_l, bb_m = self._compute_bollinger(closes)
            result.bollinger_upper, result.bollinger_lower, result.bollinger_mid = bb_u, bb_l, bb_m

            result.dcw = self._compute_dcw(dc_u, dc_l)
            result.current_dcw = result.dcw[-1] if result.dcw else 0.0

            if result.atr:
                valid_atr = [a for a in result.atr if a > 0]
                if valid_atr:
                    sorted_atr = sorted(valid_atr)
                    rank = sum(1 for a in sorted_atr if a <= result.current_atr)
                    result.atr_percentile = round((rank / len(sorted_atr)) * 100, 1)

            result.is_valid = True
        except Exception as e:
            result.error = str(e)
            logger.error("indicator_computation_failed", product=product, error=str(e))

        self._cache[cache_key] = result
        return result

    def compute_spread_indicators(self, spread_bars: list[SpreadBar], product: str, use_cache: bool = True) -> IndicatorResult:
        """Compute indicators for a spread bar series (basis points)."""
        cache_key = self._cache_key(f"spread_{product}", spread_bars)
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        result = IndicatorResult(product=product, bar_count=len(spread_bars))
        if len(spread_bars) < self._min_bars:
            result.insufficient_bars = True
            result.error = f"Insufficient spread bars: {len(spread_bars)} < {self._min_bars}"
            return result

        try:
            closes_bp = np.array([b.close_bp for b in spread_bars], dtype=np.float64)
            highs_bp = np.array([b.high_bp for b in spread_bars], dtype=np.float64)
            lows_bp = np.array([b.low_bp for b in spread_bars], dtype=np.float64)

            result.atr = self._compute_atr(highs_bp, lows_bp, closes_bp)
            result.current_atr = result.atr[-1] if result.atr else 0.0
            result.sma_fast = self._compute_sma(closes_bp, self._ma_fast)
            result.sma_slow = self._compute_sma(closes_bp, self._ma_slow)

            dc_u, dc_l, dc_m = self._compute_donchian(highs_bp, lows_bp)
            result.donchian_upper, result.donchian_lower, result.donchian_mid = dc_u, dc_l, dc_m
            result.current_donchian_upper = dc_u[-1] if dc_u else 0.0
            result.current_donchian_lower = dc_l[-1] if dc_l else 0.0

            result.dcw = self._compute_dcw(dc_u, dc_l)
            result.current_dcw = result.dcw[-1] if result.dcw else 0.0

            result.spread_sma = self._compute_sma(closes_bp, self._spread_sma_length)
            if result.spread_sma:
                result.spread_delta = [round(closes_bp[i] - result.spread_sma[i], 4) for i in range(len(result.spread_sma))]

            if result.atr:
                valid_atr = [a for a in result.atr if a > 0]
                if valid_atr:
                    sorted_atr = sorted(valid_atr)
                    rank = sum(1 for a in sorted_atr if a <= result.current_atr)
                    result.atr_percentile = round((rank / len(sorted_atr)) * 100, 1)

            result.is_valid = True
        except Exception as e:
            result.error = str(e)
            logger.error("spread_indicator_failed", product=product, error=str(e))

        self._cache[cache_key] = result
        return result

    def invalidate_cache(self, product: Optional[str] = None) -> None:
        if product:
            keys = [k for k in self._cache if product in k]
            for k in keys:
                del self._cache[k]
        else:
            self._cache.clear()

    # ── ATR (Wilder Smoothing) ────────────────────────────────
    def _compute_atr(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> list[float]:
        """TR = max(H-L, |H-prev_close|, |L-prev_close|). ATR[i] = ((ATR[i-1]*(N-1))+TR[i])/N"""
        n = len(closes)
        if n < 2:
            return []
        tr = np.zeros(n)
        tr[0] = highs[0] - lows[0]
        for i in range(1, n):
            tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        period = self._atr_length
        atr = np.zeros(n)
        if n < period:
            return []
        atr[period - 1] = np.mean(tr[:period])
        for i in range(period, n):
            atr[i] = ((atr[i - 1] * (period - 1)) + tr[i]) / period
        return [round(float(v), 6) for v in atr]

    # ── SMA ───────────────────────────────────────────────────
    def _compute_sma(self, data: np.ndarray, period: int) -> list[float]:
        if len(data) < period:
            return []
        sma = np.convolve(data, np.ones(period) / period, mode="valid")
        padding = [0.0] * (period - 1)
        return padding + [round(float(v), 6) for v in sma]

    # ── EMA ───────────────────────────────────────────────────
    def _compute_ema(self, data: np.ndarray, period: int) -> list[float]:
        if len(data) < period:
            return []
        mult = 2.0 / (period + 1)
        ema = np.zeros(len(data))
        ema[period - 1] = np.mean(data[:period])
        for i in range(period, len(data)):
            ema[i] = (data[i] - ema[i - 1]) * mult + ema[i - 1]
        return [round(float(v), 6) for v in ema]

    # ── Donchian ──────────────────────────────────────────────
    def _compute_donchian(self, highs: np.ndarray, lows: np.ndarray) -> tuple[list[float], list[float], list[float]]:
        period = self._donchian_length
        n = len(highs)
        if n < period:
            return [], [], []
        upper, lower, mid = [], [], []
        for i in range(n):
            if i < period - 1:
                upper.append(0.0); lower.append(0.0); mid.append(0.0)
            else:
                h = float(np.max(highs[i - period + 1: i + 1]))
                lo = float(np.min(lows[i - period + 1: i + 1]))
                upper.append(round(h, 6)); lower.append(round(lo, 6)); mid.append(round((h + lo) / 2, 6))
        return upper, lower, mid

    # ── Bollinger ─────────────────────────────────────────────
    def _compute_bollinger(self, data: np.ndarray) -> tuple[list[float], list[float], list[float]]:
        period = self._bollinger_length
        std_m = self._bollinger_std
        n = len(data)
        if n < period:
            return [], [], []
        upper, lower, mid = [], [], []
        for i in range(n):
            if i < period - 1:
                upper.append(0.0); lower.append(0.0); mid.append(0.0)
            else:
                w = data[i - period + 1: i + 1]
                s = float(np.mean(w))
                sd = float(np.std(w, ddof=1))
                upper.append(round(s + std_m * sd, 6)); lower.append(round(s - std_m * sd, 6)); mid.append(round(s, 6))
        return upper, lower, mid

    # ── DCW ───────────────────────────────────────────────────
    def _compute_dcw(self, dc_upper: list[float], dc_lower: list[float]) -> list[float]:
        return [round(u - lo, 6) for u, lo in zip(dc_upper, dc_lower)]

    @staticmethod
    def _cache_key(product: str, bars: list) -> str:
        if not bars:
            return f"{product}_empty"
        return f"{product}_{len(bars)}_{bars[0].timestamp}_{bars[-1].timestamp}"
