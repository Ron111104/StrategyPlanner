"""
Indicator computation engine for CME Fed Funds Futures (ZQ) Strategy Planning Platform.

Provides ATR (Wilder's smoothing), SMA, EMA, Donchian Channels,
Bollinger Bands, and DCW calculations with caching and NumPy acceleration.
"""
from __future__ import annotations

import hashlib
from typing import Any

import numpy as np
import structlog

from app.contracts.market_data import OHLCVBar, IndicatorConfig
from app.core.exceptions import InsufficientDataError, IndicatorError
from app.utils.math_helpers import wilder_smooth, safe_divide

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class IndicatorEngine:
    """Computes and caches technical indicators for ZQ futures."""

    __slots__ = ("_indicator_cache",)

    def __init__(self) -> None:
        # Cache keyed by (product, timeframe, indicator_name, length)
        self._indicator_cache: dict[tuple[str, str, str, int], Any] = {}

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------
    def _cache_key(
        self,
        product: str,
        timeframe: str,
        indicator: str,
        length: int,
    ) -> tuple[str, str, str, int]:
        return (product, timeframe, indicator, length)

    def _put_cache(
        self,
        key: tuple[str, str, str, int],
        value: Any,
    ) -> None:
        self._indicator_cache[key] = value

    def _get_cache(
        self,
        key: tuple[str, str, str, int],
    ) -> Any | None:
        return self._indicator_cache.get(key)

    def clear_cache(self) -> None:
        """Clear the entire indicator cache."""
        self._indicator_cache.clear()
        logger.info("indicator_cache_cleared")

    # ------------------------------------------------------------------
    # ATR – Wilder's smoothing
    # ------------------------------------------------------------------
    def compute_atr(
        self,
        bars: list[OHLCVBar],
        length: int = 14,
    ) -> list[float]:
        """Compute Average True Range using Wilder's smoothing.

        Parameters
        ----------
        bars:
            OHLCV bar data.  Must have at least ``length + 1`` bars
            (we need a previous close for the first TR).
        length:
            Lookback period (default 14).

        Returns
        -------
        list[float]
            ATR values aligned to *bars* – the first ``length`` entries are
            ``float('nan')`` because the ATR is undefined until we have a full
            window.

        Raises
        ------
        InsufficientDataError
            If ``len(bars) < length + 1``.
        """
        min_required = length + 1
        if len(bars) < min_required:
            raise InsufficientDataError(
                f"ATR({length}) requires at least {min_required} bars, "
                f"got {len(bars)}"
            )

        highs = np.array([b.high for b in bars], dtype=np.float64)
        lows = np.array([b.low for b in bars], dtype=np.float64)
        closes = np.array([b.close for b in bars], dtype=np.float64)

        # True Range: max(H-L, |H-prevC|, |L-prevC|)
        prev_closes = np.roll(closes, 1)
        prev_closes[0] = closes[0]  # first bar: no prev close, use own close

        hl = highs - lows
        hpc = np.abs(highs - prev_closes)
        lpc = np.abs(lows - prev_closes)

        true_range = np.maximum(hl, np.maximum(hpc, lpc))

        # Wilder's smoothing
        atr_values = np.full(len(bars), np.nan, dtype=np.float64)
        # First ATR = SMA of first *length* true ranges (indices 1..length)
        first_atr = np.mean(true_range[1 : length + 1])
        atr_values[length] = first_atr

        for i in range(length + 1, len(bars)):
            atr_values[i] = (
                atr_values[i - 1] * (length - 1) + true_range[i]
            ) / length

        result = atr_values.tolist()
        logger.debug("compute_atr_done", length=length, bar_count=len(bars))
        return result

    # ------------------------------------------------------------------
    # SMA
    # ------------------------------------------------------------------
    def compute_sma(
        self,
        values: list[float],
        length: int,
    ) -> list[float]:
        """Simple Moving Average over *length* periods.

        Returns a list of the same length as *values*; the first ``length - 1``
        entries are ``float('nan')``.
        """
        if len(values) < length:
            raise InsufficientDataError(
                f"SMA({length}) requires at least {length} values, "
                f"got {len(values)}"
            )

        arr = np.array(values, dtype=np.float64)
        cumsum = np.cumsum(arr)
        sma = np.full(len(arr), np.nan, dtype=np.float64)
        sma[length - 1 :] = (cumsum[length - 1 :] - np.concatenate(([0.0], cumsum[: -length]))) / length

        result = sma.tolist()
        logger.debug("compute_sma_done", length=length, value_count=len(values))
        return result

    # ------------------------------------------------------------------
    # EMA
    # ------------------------------------------------------------------
    def compute_ema(
        self,
        values: list[float],
        length: int,
    ) -> list[float]:
        """Exponential Moving Average.

        Seed with SMA of first *length* values, then apply:
            EMA_t = (value_t - EMA_{t-1}) * multiplier + EMA_{t-1}
        """
        if len(values) < length:
            raise InsufficientDataError(
                f"EMA({length}) requires at least {length} values, "
                f"got {len(values)}"
            )

        arr = np.array(values, dtype=np.float64)
        multiplier = 2.0 / (length + 1)

        ema = np.full(len(arr), np.nan, dtype=np.float64)
        # Seed: SMA of first *length* values
        ema[length - 1] = np.mean(arr[:length])

        for i in range(length, len(arr)):
            ema[i] = (arr[i] - ema[i - 1]) * multiplier + ema[i - 1]

        result = ema.tolist()
        logger.debug("compute_ema_done", length=length, value_count=len(values))
        return result

    # ------------------------------------------------------------------
    # Donchian Channels
    # ------------------------------------------------------------------
    def compute_donchian(
        self,
        bars: list[OHLCVBar],
        length: int = 20,
    ) -> dict[str, list[float]]:
        """Donchian Channels: rolling max(high) / min(low) over *length*.

        Returns ``{'upper': [...], 'lower': [...], 'mid': [...]}``.
        """
        if len(bars) < length:
            raise InsufficientDataError(
                f"Donchian({length}) requires at least {length} bars, "
                f"got {len(bars)}"
            )

        highs = np.array([b.high for b in bars], dtype=np.float64)
        lows = np.array([b.low for b in bars], dtype=np.float64)

        n = len(bars)
        upper = np.full(n, np.nan, dtype=np.float64)
        lower = np.full(n, np.nan, dtype=np.float64)

        # Use a sliding window via stride tricks for efficiency
        for i in range(length - 1, n):
            window_start = i - length + 1
            upper[i] = np.max(highs[window_start : i + 1])
            lower[i] = np.min(lows[window_start : i + 1])

        mid = (upper + lower) / 2.0

        result = {
            "upper": upper.tolist(),
            "lower": lower.tolist(),
            "mid": mid.tolist(),
        }
        logger.debug("compute_donchian_done", length=length, bar_count=len(bars))
        return result

    # ------------------------------------------------------------------
    # Bollinger Bands
    # ------------------------------------------------------------------
    def compute_bollinger(
        self,
        bars: list[OHLCVBar],
        length: int = 20,
        std_dev: float = 2.0,
    ) -> dict[str, list[float]]:
        """Bollinger Bands: SMA ± std_dev * rolling std.

        Returns ``{'upper': [...], 'lower': [...], 'mid': [...]}``.
        """
        if len(bars) < length:
            raise InsufficientDataError(
                f"Bollinger({length}) requires at least {length} bars, "
                f"got {len(bars)}"
            )

        closes = np.array([b.close for b in bars], dtype=np.float64)

        sma_values = np.array(self.compute_sma(closes.tolist(), length), dtype=np.float64)

        # Rolling std (population std to match typical charting convention)
        n = len(closes)
        rolling_std = np.full(n, np.nan, dtype=np.float64)
        for i in range(length - 1, n):
            window = closes[i - length + 1 : i + 1]
            rolling_std[i] = np.std(window, ddof=0)

        upper = sma_values + std_dev * rolling_std
        lower = sma_values - std_dev * rolling_std

        result = {
            "upper": upper.tolist(),
            "lower": lower.tolist(),
            "mid": sma_values.tolist(),
        }
        logger.debug(
            "compute_bollinger_done",
            length=length,
            std_dev=std_dev,
            bar_count=len(bars),
        )
        return result

    # ------------------------------------------------------------------
    # DCW – Donchian Channel Width
    # ------------------------------------------------------------------
    def compute_dcw(
        self,
        bars: list[OHLCVBar],
        length: int = 20,
    ) -> list[float]:
        """Donchian Channel Width: (upper - lower) / mid.

        Returns NaN for indices where Donchian is undefined.
        """
        donchian = self.compute_donchian(bars, length)
        upper = np.array(donchian["upper"], dtype=np.float64)
        lower = np.array(donchian["lower"], dtype=np.float64)
        mid = np.array(donchian["mid"], dtype=np.float64)

        # safe_divide at array level: where mid == 0, result is NaN
        with np.errstate(divide="ignore", invalid="ignore"):
            dcw = np.where(mid != 0.0, (upper - lower) / mid, np.nan)

        result = dcw.tolist()
        logger.debug("compute_dcw_done", length=length, bar_count=len(bars))
        return result

    # ------------------------------------------------------------------
    # compute_all – one-shot indicator computation
    # ------------------------------------------------------------------
    def compute_all(
        self,
        bars: list[OHLCVBar],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Compute all configured indicators in one pass.

        Parameters
        ----------
        bars:
            OHLCV bar data.
        config:
            Indicator configuration dict.  Recognised keys:
            - ``atr_length`` (int, default 14)
            - ``sma_length`` (int, default 20)
            - ``ema_length`` (int, default 21)
            - ``donchian_length`` (int, default 20)
            - ``bollinger_length`` (int, default 20)
            - ``bollinger_std`` (float, default 2.0)
            - ``dcw_length`` (int, default 20)

        Returns
        -------
        dict[str, Any]
            Keyed by indicator name: ``atr``, ``sma``, ``ema``,
            ``donchian``, ``bollinger``, ``dcw``.  Each value is the
            respective compute_* return type.
        """
        atr_len: int = config.get("atr_length", 14)
        sma_len: int = config.get("sma_length", 20)
        ema_len: int = config.get("ema_length", 21)
        donchian_len: int = config.get("donchian_length", 20)
        bollinger_len: int = config.get("bollinger_length", 20)
        bollinger_std: float = config.get("bollinger_std", 2.0)
        dcw_len: int = config.get("dcw_length", 20)

        closes = [b.close for b in bars]

        results: dict[str, Any] = {}

        # ATR
        try:
            results["atr"] = self.compute_atr(bars, atr_len)
        except InsufficientDataError:
            logger.warning("insufficient_data_for_atr", length=atr_len, bars=len(bars))
            results["atr"] = []

        # SMA
        try:
            results["sma"] = self.compute_sma(closes, sma_len)
        except InsufficientDataError:
            logger.warning("insufficient_data_for_sma", length=sma_len, bars=len(bars))
            results["sma"] = []

        # EMA
        try:
            results["ema"] = self.compute_ema(closes, ema_len)
        except InsufficientDataError:
            logger.warning("insufficient_data_for_ema", length=ema_len, bars=len(bars))
            results["ema"] = []

        # Donchian
        try:
            results["donchian"] = self.compute_donchian(bars, donchian_len)
        except InsufficientDataError:
            logger.warning(
                "insufficient_data_for_donchian",
                length=donchian_len,
                bars=len(bars),
            )
            results["donchian"] = {"upper": [], "lower": [], "mid": []}

        # Bollinger
        try:
            results["bollinger"] = self.compute_bollinger(bars, bollinger_len, bollinger_std)
        except InsufficientDataError:
            logger.warning(
                "insufficient_data_for_bollinger",
                length=bollinger_len,
                bars=len(bars),
            )
            results["bollinger"] = {"upper": [], "lower": [], "mid": []}

        # DCW
        try:
            results["dcw"] = self.compute_dcw(bars, dcw_len)
        except InsufficientDataError:
            logger.warning("insufficient_data_for_dcw", length=dcw_len, bars=len(bars))
            results["dcw"] = []

        # ATR SMA (useful for regime classification)
        if results["atr"]:
            valid_atr = [v for v in results["atr"] if not (isinstance(v, float) and np.isnan(v))]
            if len(valid_atr) >= sma_len:
                results["atr_sma"] = self.compute_sma(valid_atr, sma_len)
            else:
                results["atr_sma"] = []
        else:
            results["atr_sma"] = []

        logger.info(
            "compute_all_done",
            bar_count=len(bars),
            indicators=list(results.keys()),
        )
        return results
