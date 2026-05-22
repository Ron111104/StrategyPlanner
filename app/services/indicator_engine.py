"""Institutional indicator computation engine.

Indicators: SMA, EMA, HMA, KAMA, VWAP, Anchored VWAP, ATR, NATR,
Historical Vol, Realized Vol, Bollinger Width, DCW, Keltner, RSI,
Stochastic RSI, MACD, ROC, Momentum, PPO, Donchian, Bollinger,
Range Compression, Expansion Detection, Session Range, Spread Z-score,
Spread Mean Deviation, Spread Velocity, Spread Acceleration, Curve Slope,
Curve Momentum, Spread ATR, Spread DCW, Relative Volume, Volume Delta.
"""
from typing import Optional
import math

import numpy as np

from app.config.loader import load_strategy_settings
from app.contracts.indicators import IndicatorResult, IndicatorSet
from app.contracts.market_data import OHLCVSeries
from app.core.exceptions import InsufficientDataError, IndicatorError
from app.core.logging import get_logger
from app.services.cache import CacheManager

logger = get_logger(__name__)


def _extract(arr: np.ndarray, bars: list, mask: np.ndarray | None = None):
    """Extract valid values and timestamps."""
    if mask is None:
        mask = ~np.isnan(arr)
    vals = arr[mask].tolist()
    ts = [bars[i].timestamp for i in range(len(arr)) if mask[i]]
    return vals, ts


class IndicatorEngine:
    """Computes technical indicators on OHLCV series."""

    def __init__(self) -> None:
        self._cache = CacheManager()
        self._settings = load_strategy_settings().get("indicators", {})

    # ===================== ORCHESTRATION =====================

    def compute_all(self, series: OHLCVSeries) -> IndicatorSet:
        """Compute all configured indicators for a series."""
        if series.is_empty:
            raise InsufficientDataError(f"No bars for {series.symbol}")

        ind = IndicatorSet(symbol=series.symbol, timeframe=series.timeframe)

        def _safe(fn, *a, **kw):
            try:
                return fn(*a, **kw)
            except InsufficientDataError:
                return None
            except Exception as e:
                logger.warning("indicator_error", fn=fn.__name__, error=str(e))
                return None

        # --- Trend ---
        for ln in self._settings.get("sma", {}).get("default_lengths", [20, 50]):
            r = _safe(self.compute_sma, series, ln)
            if r:
                ind.sma[ln] = r
        for ln in self._settings.get("ema", {}).get("default_lengths", [9, 21]):
            r = _safe(self.compute_ema, series, ln)
            if r:
                ind.ema[ln] = r
        for ln in self._settings.get("hma", {}).get("default_lengths", [9]):
            r = _safe(self.compute_hma, series, ln)
            if r:
                ind.hma[ln] = r
        for ln in self._settings.get("kama", {}).get("default_lengths", [10]):
            r = _safe(self.compute_kama, series, ln)
            if r:
                ind.kama[ln] = r
        ind.vwap = _safe(self.compute_vwap, series)
        ind.anchored_vwap = _safe(self.compute_anchored_vwap, series)

        # --- Volatility ---
        atr_len = self._settings.get("atr", {}).get("default_length", 14)
        ind.atr = _safe(self.compute_atr, series, atr_len)
        ind.natr = _safe(self.compute_natr, series, atr_len)
        ind.historical_vol = _safe(self.compute_historical_vol, series, 20)
        ind.realized_vol = _safe(self.compute_realized_vol, series, 20)
        bb_len = self._settings.get("bollinger", {}).get("default_length", 20)
        bb_std = self._settings.get("bollinger", {}).get("default_std_dev", 2.0)
        ind.bollinger = _safe(self.compute_bollinger, series, bb_len, bb_std)
        ind.bollinger_width = _safe(self.compute_bollinger_width, series, bb_len, bb_std)
        dcw_len = self._settings.get("dcw", {}).get("default_length", 20)
        ind.dcw = _safe(self.compute_dcw, series, dcw_len)
        ind.keltner = _safe(self.compute_keltner, series, 20, 1.5)

        # --- Momentum ---
        ind.rsi = _safe(self.compute_rsi, series, 14)
        ind.stoch_rsi = _safe(self.compute_stoch_rsi, series, 14, 14, 3, 3)
        ind.macd = _safe(self.compute_macd, series, 12, 26, 9)
        ind.roc = _safe(self.compute_roc, series, 14)
        ind.momentum = _safe(self.compute_momentum, series, 14)
        ind.ppo = _safe(self.compute_ppo, series, 12, 26, 9)

        # --- Structure ---
        dc_len = self._settings.get("donchian", {}).get("default_length", 20)
        ind.donchian = _safe(self.compute_donchian, series, dc_len)
        ind.range_compression = _safe(self.compute_range_compression, series, 20)
        ind.expansion_detection = _safe(self.compute_expansion_detection, series, 20)
        ind.session_range = _safe(self.compute_session_range, series)

        # --- Spread (only for spread symbols) ---
        if "-" in series.symbol:
            ind.spread_zscore = _safe(self.compute_spread_zscore, series, 20)
            ind.spread_mean_dev = _safe(self.compute_spread_mean_deviation, series, 20)
            ind.spread_velocity = _safe(self.compute_spread_velocity, series, 5)
            ind.spread_acceleration = _safe(self.compute_spread_acceleration, series, 5)
            ind.curve_slope = _safe(self.compute_curve_slope, series, 10)
            ind.curve_momentum = _safe(self.compute_curve_momentum, series, 10)
            ind.spread_atr = _safe(self.compute_atr, series, atr_len)
            ind.spread_dcw = _safe(self.compute_dcw, series, dcw_len)

        # --- Liquidity ---
        ind.relative_volume = _safe(self.compute_relative_volume, series, 20)
        ind.volume_delta = _safe(self.compute_volume_delta, series)

        self._cache.set_indicators(series.symbol, series.timeframe, ind)
        return ind

    # ===================== TREND INDICATORS =====================

    def compute_sma(self, series: OHLCVSeries, length: int = 20) -> IndicatorResult:
        """Simple Moving Average."""
        if series.length < length:
            raise InsufficientDataError(f"Need {length} bars for SMA({length}), have {series.length}")
        closes = np.array(series.closes(), dtype=np.float64)
        sma = np.full(len(closes), np.nan)
        for i in range(length - 1, len(closes)):
            sma[i] = np.mean(closes[i - length + 1: i + 1])
        vals, ts = _extract(sma, series.bars)
        return IndicatorResult(name=f"SMA_{length}", symbol=series.symbol, timeframe=series.timeframe, values=vals, timestamps=ts, params={"length": float(length)})

    def compute_ema(self, series: OHLCVSeries, length: int = 21) -> IndicatorResult:
        """Exponential Moving Average."""
        if series.length < length:
            raise InsufficientDataError(f"Need {length} bars for EMA({length}), have {series.length}")
        closes = np.array(series.closes(), dtype=np.float64)
        m = 2.0 / (length + 1)
        ema = np.full(len(closes), np.nan)
        ema[length - 1] = np.mean(closes[:length])
        for i in range(length, len(closes)):
            ema[i] = (closes[i] - ema[i - 1]) * m + ema[i - 1]
        vals, ts = _extract(ema, series.bars)
        return IndicatorResult(name=f"EMA_{length}", symbol=series.symbol, timeframe=series.timeframe, values=vals, timestamps=ts, params={"length": float(length)})

    def _wma(self, data: np.ndarray, length: int) -> np.ndarray:
        """Weighted Moving Average helper."""
        wma = np.full(len(data), np.nan)
        weights = np.arange(1, length + 1, dtype=np.float64)
        w_sum = weights.sum()
        for i in range(length - 1, len(data)):
            wma[i] = np.dot(data[i - length + 1: i + 1], weights) / w_sum
        return wma

    def compute_hma(self, series: OHLCVSeries, length: int = 9) -> IndicatorResult:
        """Hull Moving Average: WMA(2*WMA(n/2) - WMA(n), sqrt(n))."""
        half = max(1, length // 2)
        sqrt_n = max(1, int(math.sqrt(length)))
        needed = length + sqrt_n
        if series.length < needed:
            raise InsufficientDataError(f"Need {needed} bars for HMA({length}), have {series.length}")
        closes = np.array(series.closes(), dtype=np.float64)
        wma_half = self._wma(closes, half)
        wma_full = self._wma(closes, length)
        raw = 2.0 * wma_half - wma_full
        hma = self._wma(raw, sqrt_n)
        vals, ts = _extract(hma, series.bars)
        return IndicatorResult(name=f"HMA_{length}", symbol=series.symbol, timeframe=series.timeframe, values=vals, timestamps=ts, params={"length": float(length)})

    def compute_kama(self, series: OHLCVSeries, length: int = 10, fast: int = 2, slow: int = 30) -> IndicatorResult:
        """Kaufman Adaptive Moving Average."""
        if series.length < length + 1:
            raise InsufficientDataError(f"Need {length + 1} bars for KAMA({length}), have {series.length}")
        closes = np.array(series.closes(), dtype=np.float64)
        fast_sc = 2.0 / (fast + 1)
        slow_sc = 2.0 / (slow + 1)
        kama = np.full(len(closes), np.nan)
        kama[length] = closes[length]
        for i in range(length + 1, len(closes)):
            direction = abs(closes[i] - closes[i - length])
            volatility = sum(abs(closes[j] - closes[j - 1]) for j in range(i - length + 1, i + 1))
            er = direction / volatility if volatility > 0 else 0.0
            sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
            kama[i] = kama[i - 1] + sc * (closes[i] - kama[i - 1])
        vals, ts = _extract(kama, series.bars)
        return IndicatorResult(name=f"KAMA_{length}", symbol=series.symbol, timeframe=series.timeframe, values=vals, timestamps=ts, params={"length": float(length)})

    def compute_vwap(self, series: OHLCVSeries) -> IndicatorResult:
        """Volume Weighted Average Price (rolling session)."""
        if series.length < 2:
            raise InsufficientDataError("Need >=2 bars for VWAP")
        tp = np.array([(b.high + b.low + b.close) / 3.0 for b in series.bars], dtype=np.float64)
        vol = np.array(series.volumes(), dtype=np.float64)
        cum_tpv = np.cumsum(tp * vol)
        cum_vol = np.cumsum(vol)
        vwap = np.where(cum_vol > 0, cum_tpv / cum_vol, np.nan)
        vals, ts = _extract(vwap, series.bars)
        return IndicatorResult(name="VWAP", symbol=series.symbol, timeframe=series.timeframe, values=vals, timestamps=ts)

    def compute_anchored_vwap(self, series: OHLCVSeries, anchor_idx: int = 0) -> IndicatorResult:
        """Anchored VWAP from a specific bar index (default: first bar)."""
        if series.length < 2:
            raise InsufficientDataError("Need >=2 bars for Anchored VWAP")
        tp = np.array([(b.high + b.low + b.close) / 3.0 for b in series.bars], dtype=np.float64)
        vol = np.array(series.volumes(), dtype=np.float64)
        avwap = np.full(len(tp), np.nan)
        cum_tpv = 0.0
        cum_vol = 0.0
        for i in range(anchor_idx, len(tp)):
            cum_tpv += tp[i] * vol[i]
            cum_vol += vol[i]
            avwap[i] = cum_tpv / cum_vol if cum_vol > 0 else np.nan
        vals, ts = _extract(avwap, series.bars)
        return IndicatorResult(name="AVWAP", symbol=series.symbol, timeframe=series.timeframe, values=vals, timestamps=ts, params={"anchor_idx": float(anchor_idx)})

    # ===================== VOLATILITY INDICATORS =====================

    def compute_atr(self, series: OHLCVSeries, length: int = 14) -> IndicatorResult:
        """ATR with Wilder smoothing."""
        if series.length < length + 1:
            raise InsufficientDataError(f"Need {length + 1} bars for ATR({length}), have {series.length}")
        highs = np.array(series.highs(), dtype=np.float64)
        lows = np.array(series.lows(), dtype=np.float64)
        closes = np.array(series.closes(), dtype=np.float64)
        tr = np.empty(len(highs))
        tr[0] = highs[0] - lows[0]
        for i in range(1, len(highs)):
            tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        atr = np.full(len(tr), np.nan)
        atr[length] = np.mean(tr[1: length + 1])
        for i in range(length + 1, len(tr)):
            atr[i] = (atr[i - 1] * (length - 1) + tr[i]) / length
        vals, ts = _extract(atr, series.bars)
        return IndicatorResult(name="ATR", symbol=series.symbol, timeframe=series.timeframe, values=vals, timestamps=ts, params={"length": float(length)})

    def compute_natr(self, series: OHLCVSeries, length: int = 14) -> IndicatorResult:
        """Normalized ATR (ATR / close * 100)."""
        atr_result = self.compute_atr(series, length)
        closes = np.array(series.closes(), dtype=np.float64)
        offset = series.length - len(atr_result.values)
        natr_vals = [(atr_result.values[i] / closes[offset + i] * 100) if closes[offset + i] > 0 else 0.0 for i in range(len(atr_result.values))]
        return IndicatorResult(name="NATR", symbol=series.symbol, timeframe=series.timeframe, values=natr_vals, timestamps=atr_result.timestamps, params={"length": float(length)})

    def compute_historical_vol(self, series: OHLCVSeries, length: int = 20) -> IndicatorResult:
        """Historical Volatility (annualized std of log returns)."""
        if series.length < length + 1:
            raise InsufficientDataError(f"Need {length + 1} bars for HV({length})")
        closes = np.array(series.closes(), dtype=np.float64)
        log_ret = np.log(closes[1:] / closes[:-1])
        hv = np.full(len(closes), np.nan)
        for i in range(length, len(closes)):
            window = log_ret[i - length: i]
            hv[i] = np.std(window, ddof=1) * math.sqrt(252) * 100
        vals, ts = _extract(hv, series.bars)
        return IndicatorResult(name=f"HV_{length}", symbol=series.symbol, timeframe=series.timeframe, values=vals, timestamps=ts, params={"length": float(length)})

    def compute_realized_vol(self, series: OHLCVSeries, length: int = 20) -> IndicatorResult:
        """Realized Volatility (sum of squared returns, annualized)."""
        if series.length < length + 1:
            raise InsufficientDataError(f"Need {length + 1} bars for RV({length})")
        closes = np.array(series.closes(), dtype=np.float64)
        log_ret = np.log(closes[1:] / closes[:-1])
        rv = np.full(len(closes), np.nan)
        for i in range(length, len(closes)):
            window = log_ret[i - length: i]
            rv[i] = math.sqrt(np.sum(window ** 2) * 252 / length) * 100
        vals, ts = _extract(rv, series.bars)
        return IndicatorResult(name=f"RV_{length}", symbol=series.symbol, timeframe=series.timeframe, values=vals, timestamps=ts, params={"length": float(length)})

    def compute_bollinger_width(self, series: OHLCVSeries, length: int = 20, std_dev: float = 2.0) -> IndicatorResult:
        """Bollinger Band Width = (upper - lower) / middle."""
        bb = self.compute_bollinger(series, length, std_dev)
        bw = []
        for i in range(len(bb.values)):
            mid = bb.values[i]
            bw.append((bb.upper_band[i] - bb.lower_band[i]) / mid * 100 if mid > 0 else 0.0)
        return IndicatorResult(name=f"BBW_{length}", symbol=series.symbol, timeframe=series.timeframe, values=bw, timestamps=bb.timestamps, params={"length": float(length), "std_dev": std_dev})

    def compute_dcw(self, series: OHLCVSeries, length: int = 20) -> IndicatorResult:
        """Donchian Channel Width = upper - lower."""
        if series.length < length:
            raise InsufficientDataError(f"Need {length} bars for DCW({length}), have {series.length}")
        highs = np.array(series.highs(), dtype=np.float64)
        lows = np.array(series.lows(), dtype=np.float64)
        dcw = np.full(len(highs), np.nan)
        for i in range(length - 1, len(highs)):
            dcw[i] = np.max(highs[i - length + 1: i + 1]) - np.min(lows[i - length + 1: i + 1])
        vals, ts = _extract(dcw, series.bars)
        return IndicatorResult(name=f"DCW_{length}", symbol=series.symbol, timeframe=series.timeframe, values=vals, timestamps=ts, params={"length": float(length)})

    def compute_keltner(self, series: OHLCVSeries, length: int = 20, multiplier: float = 1.5) -> IndicatorResult:
        """Keltner Channels = EMA ± multiplier * ATR."""
        ema_r = self.compute_ema(series, length)
        atr_r = self.compute_atr(series, length)
        min_len = min(len(ema_r.values), len(atr_r.values))
        ema_v = ema_r.values[-min_len:]
        atr_v = atr_r.values[-min_len:]
        ts_list = ema_r.timestamps[-min_len:]
        mid = list(ema_v)
        upper = [ema_v[i] + multiplier * atr_v[i] for i in range(min_len)]
        lower = [ema_v[i] - multiplier * atr_v[i] for i in range(min_len)]
        return IndicatorResult(name=f"Keltner_{length}", symbol=series.symbol, timeframe=series.timeframe, values=mid, timestamps=ts_list, params={"length": float(length), "multiplier": multiplier}, upper_band=upper, lower_band=lower, middle_band=mid)

    # ===================== MOMENTUM INDICATORS =====================

    def compute_rsi(self, series: OHLCVSeries, length: int = 14) -> IndicatorResult:
        """Relative Strength Index (Wilder smoothing)."""
        if series.length < length + 1:
            raise InsufficientDataError(f"Need {length + 1} bars for RSI({length})")
        closes = np.array(series.closes(), dtype=np.float64)
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        rsi = np.full(len(closes), np.nan)
        avg_gain = np.mean(gains[:length])
        avg_loss = np.mean(losses[:length])
        if avg_loss == 0:
            rsi[length] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[length] = 100.0 - (100.0 / (1.0 + rs))
        for i in range(length + 1, len(closes)):
            avg_gain = (avg_gain * (length - 1) + gains[i - 1]) / length
            avg_loss = (avg_loss * (length - 1) + losses[i - 1]) / length
            if avg_loss == 0:
                rsi[i] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi[i] = 100.0 - (100.0 / (1.0 + rs))
        vals, ts = _extract(rsi, series.bars)
        return IndicatorResult(name=f"RSI_{length}", symbol=series.symbol, timeframe=series.timeframe, values=vals, timestamps=ts, params={"length": float(length)})

    def compute_stoch_rsi(self, series: OHLCVSeries, rsi_len: int = 14, stoch_len: int = 14, k_smooth: int = 3, d_smooth: int = 3) -> IndicatorResult:
        """Stochastic RSI."""
        rsi_r = self.compute_rsi(series, rsi_len)
        rsi_vals = np.array(rsi_r.values, dtype=np.float64)
        if len(rsi_vals) < stoch_len:
            raise InsufficientDataError(f"Need {stoch_len} RSI values for StochRSI")
        stoch_k = np.full(len(rsi_vals), np.nan)
        for i in range(stoch_len - 1, len(rsi_vals)):
            window = rsi_vals[i - stoch_len + 1: i + 1]
            rng = np.max(window) - np.min(window)
            stoch_k[i] = ((rsi_vals[i] - np.min(window)) / rng * 100) if rng > 0 else 50.0
        # Smooth %K
        valid = ~np.isnan(stoch_k)
        vals_k = stoch_k[valid]
        if len(vals_k) >= k_smooth:
            smoothed = np.convolve(vals_k, np.ones(k_smooth) / k_smooth, mode='valid')
        else:
            smoothed = vals_k
        ts_list = [rsi_r.timestamps[i] for i in range(len(stoch_k)) if valid[i]]
        ts_list = ts_list[-len(smoothed):]
        # %D = SMA of smoothed %K
        sig = list(np.convolve(smoothed, np.ones(d_smooth) / d_smooth, mode='valid')) if len(smoothed) >= d_smooth else list(smoothed)
        return IndicatorResult(name="StochRSI", symbol=series.symbol, timeframe=series.timeframe, values=list(smoothed), timestamps=ts_list, params={"rsi_len": float(rsi_len), "stoch_len": float(stoch_len)}, signal_line=sig)

    def compute_macd(self, series: OHLCVSeries, fast: int = 12, slow: int = 26, signal: int = 9) -> IndicatorResult:
        """MACD with signal line and histogram."""
        ema_fast = self.compute_ema(series, fast)
        ema_slow = self.compute_ema(series, slow)
        min_len = min(len(ema_fast.values), len(ema_slow.values))
        fast_v = ema_fast.values[-min_len:]
        slow_v = ema_slow.values[-min_len:]
        macd_line = [fast_v[i] - slow_v[i] for i in range(min_len)]
        ts_list = ema_fast.timestamps[-min_len:]
        # Signal line = EMA of MACD
        macd_arr = np.array(macd_line, dtype=np.float64)
        sig_m = 2.0 / (signal + 1)
        sig_line = np.full(len(macd_arr), np.nan)
        if len(macd_arr) >= signal:
            sig_line[signal - 1] = np.mean(macd_arr[:signal])
            for i in range(signal, len(macd_arr)):
                sig_line[i] = (macd_arr[i] - sig_line[i - 1]) * sig_m + sig_line[i - 1]
        hist = [(macd_arr[i] - sig_line[i]) if not np.isnan(sig_line[i]) else 0.0 for i in range(len(macd_arr))]
        sig_list = [v for v in sig_line.tolist() if not np.isnan(v)]
        return IndicatorResult(name="MACD", symbol=series.symbol, timeframe=series.timeframe, values=macd_line, timestamps=ts_list, params={"fast": float(fast), "slow": float(slow), "signal": float(signal)}, signal_line=sig_list, histogram=hist)

    def compute_roc(self, series: OHLCVSeries, length: int = 14) -> IndicatorResult:
        """Rate of Change."""
        if series.length < length + 1:
            raise InsufficientDataError(f"Need {length + 1} bars for ROC({length})")
        closes = np.array(series.closes(), dtype=np.float64)
        roc = np.full(len(closes), np.nan)
        for i in range(length, len(closes)):
            roc[i] = ((closes[i] - closes[i - length]) / closes[i - length] * 100) if closes[i - length] != 0 else 0.0
        vals, ts = _extract(roc, series.bars)
        return IndicatorResult(name=f"ROC_{length}", symbol=series.symbol, timeframe=series.timeframe, values=vals, timestamps=ts, params={"length": float(length)})

    def compute_momentum(self, series: OHLCVSeries, length: int = 14) -> IndicatorResult:
        """Price Momentum (close - close[n])."""
        if series.length < length + 1:
            raise InsufficientDataError(f"Need {length + 1} bars for Momentum({length})")
        closes = np.array(series.closes(), dtype=np.float64)
        mom = np.full(len(closes), np.nan)
        for i in range(length, len(closes)):
            mom[i] = closes[i] - closes[i - length]
        vals, ts = _extract(mom, series.bars)
        return IndicatorResult(name=f"MOM_{length}", symbol=series.symbol, timeframe=series.timeframe, values=vals, timestamps=ts, params={"length": float(length)})

    def compute_ppo(self, series: OHLCVSeries, fast: int = 12, slow: int = 26, signal: int = 9) -> IndicatorResult:
        """Percentage Price Oscillator."""
        ema_fast = self.compute_ema(series, fast)
        ema_slow = self.compute_ema(series, slow)
        min_len = min(len(ema_fast.values), len(ema_slow.values))
        fast_v = ema_fast.values[-min_len:]
        slow_v = ema_slow.values[-min_len:]
        ppo_line = [((fast_v[i] - slow_v[i]) / slow_v[i] * 100) if slow_v[i] != 0 else 0.0 for i in range(min_len)]
        ts_list = ema_fast.timestamps[-min_len:]
        return IndicatorResult(name="PPO", symbol=series.symbol, timeframe=series.timeframe, values=ppo_line, timestamps=ts_list, params={"fast": float(fast), "slow": float(slow)})

    # ===================== STRUCTURE INDICATORS =====================

    def compute_donchian(self, series: OHLCVSeries, length: int = 20) -> IndicatorResult:
        """Donchian Channels."""
        if series.length < length:
            raise InsufficientDataError(f"Need {length} bars for Donchian({length}), have {series.length}")
        highs = np.array(series.highs(), dtype=np.float64)
        lows = np.array(series.lows(), dtype=np.float64)
        upper = np.full(len(highs), np.nan)
        lower = np.full(len(lows), np.nan)
        middle = np.full(len(highs), np.nan)
        for i in range(length - 1, len(highs)):
            upper[i] = np.max(highs[i - length + 1: i + 1])
            lower[i] = np.min(lows[i - length + 1: i + 1])
            middle[i] = (upper[i] + lower[i]) / 2.0
        mask = ~np.isnan(upper)
        ts = [series.bars[i].timestamp for i in range(len(upper)) if mask[i]]
        return IndicatorResult(name=f"Donchian_{length}", symbol=series.symbol, timeframe=series.timeframe, values=middle[mask].tolist(), timestamps=ts, params={"length": float(length)}, upper_band=upper[mask].tolist(), lower_band=lower[mask].tolist(), middle_band=middle[mask].tolist())

    def compute_bollinger(self, series: OHLCVSeries, length: int = 20, std_dev: float = 2.0) -> IndicatorResult:
        """Bollinger Bands."""
        if series.length < length:
            raise InsufficientDataError(f"Need {length} bars for Bollinger({length}), have {series.length}")
        closes = np.array(series.closes(), dtype=np.float64)
        mid = np.full(len(closes), np.nan)
        up = np.full(len(closes), np.nan)
        lo = np.full(len(closes), np.nan)
        for i in range(length - 1, len(closes)):
            w = closes[i - length + 1: i + 1]
            m = np.mean(w)
            s = np.std(w, ddof=0)
            mid[i] = m
            up[i] = m + std_dev * s
            lo[i] = m - std_dev * s
        mask = ~np.isnan(mid)
        ts = [series.bars[i].timestamp for i in range(len(mid)) if mask[i]]
        return IndicatorResult(name=f"Bollinger_{length}_{std_dev}", symbol=series.symbol, timeframe=series.timeframe, values=mid[mask].tolist(), timestamps=ts, params={"length": float(length), "std_dev": std_dev}, upper_band=up[mask].tolist(), lower_band=lo[mask].tolist(), middle_band=mid[mask].tolist())

    def compute_range_compression(self, series: OHLCVSeries, length: int = 20) -> IndicatorResult:
        """Range Compression = current DCW / avg DCW over lookback. <1 = compressed."""
        dcw_r = self.compute_dcw(series, length)
        if len(dcw_r.values) < length:
            raise InsufficientDataError("Need more DCW values for range compression")
        vals = dcw_r.values
        rc = []
        for i in range(length - 1, len(vals)):
            avg = np.mean(vals[max(0, i - length + 1): i + 1])
            rc.append(vals[i] / avg if avg > 0 else 1.0)
        ts = dcw_r.timestamps[-len(rc):]
        return IndicatorResult(name=f"RC_{length}", symbol=series.symbol, timeframe=series.timeframe, values=rc, timestamps=ts, params={"length": float(length)})

    def compute_expansion_detection(self, series: OHLCVSeries, length: int = 20) -> IndicatorResult:
        """Expansion detection: 1.0 if current ATR > 1.5 * avg ATR, else 0.0."""
        atr_r = self.compute_atr(series, length)
        if len(atr_r.values) < length:
            raise InsufficientDataError("Need more ATR values for expansion detection")
        vals = atr_r.values
        exp = []
        for i in range(length - 1, len(vals)):
            avg = np.mean(vals[max(0, i - length + 1): i + 1])
            exp.append(1.0 if vals[i] > 1.5 * avg else 0.0)
        ts = atr_r.timestamps[-len(exp):]
        return IndicatorResult(name=f"EXP_{length}", symbol=series.symbol, timeframe=series.timeframe, values=exp, timestamps=ts, params={"length": float(length)})

    def compute_session_range(self, series: OHLCVSeries) -> IndicatorResult:
        """Session Range: high - low per bar as a rolling measure."""
        if series.length < 1:
            raise InsufficientDataError("Need >=1 bar for session range")
        vals = [b.high - b.low for b in series.bars]
        ts = [b.timestamp for b in series.bars]
        return IndicatorResult(name="SessionRange", symbol=series.symbol, timeframe=series.timeframe, values=vals, timestamps=ts)

    # ===================== SPREAD INDICATORS =====================

    def compute_spread_zscore(self, series: OHLCVSeries, length: int = 20) -> IndicatorResult:
        """Spread Z-score = (spread - SMA) / std."""
        if series.length < length:
            raise InsufficientDataError(f"Need {length} bars for spread z-score")
        closes = np.array(series.closes(), dtype=np.float64)
        zs = np.full(len(closes), np.nan)
        for i in range(length - 1, len(closes)):
            w = closes[i - length + 1: i + 1]
            m, s = np.mean(w), np.std(w, ddof=1)
            zs[i] = (closes[i] - m) / s if s > 0 else 0.0
        vals, ts = _extract(zs, series.bars)
        return IndicatorResult(name=f"SpreadZ_{length}", symbol=series.symbol, timeframe=series.timeframe, values=vals, timestamps=ts, params={"length": float(length)})

    def compute_spread_mean_deviation(self, series: OHLCVSeries, length: int = 20) -> IndicatorResult:
        """Spread deviation from rolling mean in price units."""
        if series.length < length:
            raise InsufficientDataError(f"Need {length} bars")
        closes = np.array(series.closes(), dtype=np.float64)
        dev = np.full(len(closes), np.nan)
        for i in range(length - 1, len(closes)):
            dev[i] = closes[i] - np.mean(closes[i - length + 1: i + 1])
        vals, ts = _extract(dev, series.bars)
        return IndicatorResult(name=f"SpreadMeanDev_{length}", symbol=series.symbol, timeframe=series.timeframe, values=vals, timestamps=ts, params={"length": float(length)})

    def compute_spread_velocity(self, series: OHLCVSeries, length: int = 5) -> IndicatorResult:
        """Spread velocity = rate of change over short window."""
        if series.length < length + 1:
            raise InsufficientDataError(f"Need {length + 1} bars")
        closes = np.array(series.closes(), dtype=np.float64)
        vel = np.full(len(closes), np.nan)
        for i in range(length, len(closes)):
            vel[i] = closes[i] - closes[i - length]
        vals, ts = _extract(vel, series.bars)
        return IndicatorResult(name=f"SpreadVel_{length}", symbol=series.symbol, timeframe=series.timeframe, values=vals, timestamps=ts, params={"length": float(length)})

    def compute_spread_acceleration(self, series: OHLCVSeries, length: int = 5) -> IndicatorResult:
        """Spread acceleration = diff of velocity."""
        vel_r = self.compute_spread_velocity(series, length)
        if len(vel_r.values) < 2:
            raise InsufficientDataError("Need >=2 velocity values for acceleration")
        acc = [vel_r.values[i] - vel_r.values[i - 1] for i in range(1, len(vel_r.values))]
        ts = vel_r.timestamps[1:]
        return IndicatorResult(name=f"SpreadAcc_{length}", symbol=series.symbol, timeframe=series.timeframe, values=acc, timestamps=ts, params={"length": float(length)})

    def compute_curve_slope(self, series: OHLCVSeries, length: int = 10) -> IndicatorResult:
        """Curve slope = linear regression slope of spread over window."""
        if series.length < length:
            raise InsufficientDataError(f"Need {length} bars for curve slope")
        closes = np.array(series.closes(), dtype=np.float64)
        x = np.arange(length, dtype=np.float64)
        slope = np.full(len(closes), np.nan)
        for i in range(length - 1, len(closes)):
            y = closes[i - length + 1: i + 1]
            slope[i] = np.polyfit(x, y, 1)[0]
        vals, ts = _extract(slope, series.bars)
        return IndicatorResult(name=f"CurveSlope_{length}", symbol=series.symbol, timeframe=series.timeframe, values=vals, timestamps=ts, params={"length": float(length)})

    def compute_curve_momentum(self, series: OHLCVSeries, length: int = 10) -> IndicatorResult:
        """Curve momentum = change of curve slope."""
        slope_r = self.compute_curve_slope(series, length)
        if len(slope_r.values) < 2:
            raise InsufficientDataError("Need >=2 slope values for curve momentum")
        mom = [slope_r.values[i] - slope_r.values[i - 1] for i in range(1, len(slope_r.values))]
        ts = slope_r.timestamps[1:]
        return IndicatorResult(name=f"CurveMom_{length}", symbol=series.symbol, timeframe=series.timeframe, values=mom, timestamps=ts, params={"length": float(length)})

    # ===================== LIQUIDITY INDICATORS =====================

    def compute_relative_volume(self, series: OHLCVSeries, length: int = 20) -> IndicatorResult:
        """Relative Volume = current vol / avg vol."""
        if series.length < length:
            raise InsufficientDataError(f"Need {length} bars for RelVol")
        vols = np.array(series.volumes(), dtype=np.float64)
        rv = np.full(len(vols), np.nan)
        for i in range(length - 1, len(vols)):
            avg = np.mean(vols[i - length + 1: i + 1])
            rv[i] = vols[i] / avg if avg > 0 else 1.0
        vals, ts = _extract(rv, series.bars)
        return IndicatorResult(name=f"RelVol_{length}", symbol=series.symbol, timeframe=series.timeframe, values=vals, timestamps=ts, params={"length": float(length)})

    def compute_volume_delta(self, series: OHLCVSeries) -> IndicatorResult:
        """Volume Delta proxy: vol * sign(close - open)."""
        if series.length < 1:
            raise InsufficientDataError("Need >=1 bar for volume delta")
        vd = []
        for b in series.bars:
            sign = 1.0 if b.close >= b.open else -1.0
            vd.append(b.volume * sign)
        ts = [b.timestamp for b in series.bars]
        return IndicatorResult(name="VolDelta", symbol=series.symbol, timeframe=series.timeframe, values=vd, timestamps=ts)
