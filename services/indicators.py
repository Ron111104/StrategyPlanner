"""Technical indicators — SMA, EMA, VWAP, ATR, RSI, Bollinger Bands."""

import pandas as pd
import numpy as np


def sma(df: pd.DataFrame, period: int = 20, col: str = "close") -> pd.Series:
    return df[col].rolling(period).mean()


def ema(df: pd.DataFrame, period: int = 20, col: str = "close") -> pd.Series:
    return df[col].ewm(span=period, adjust=False).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([h - l, (h - c).abs(), (l - c).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def rsi(df: pd.DataFrame, period: int = 14, col: str = "close") -> pd.Series:
    delta = df[col].diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def bollinger(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0, col: str = "close"):
    """Returns (mid, upper, lower) as Series."""
    mid = df[col].rolling(period).mean()
    std = df[col].rolling(period).std()
    return mid, mid + std_dev * std, mid - std_dev * std


def vwap(df: pd.DataFrame) -> pd.Series:
    """Cumulative VWAP from start of dataframe (session or full history)."""
    typical = (df["high"] + df["low"] + df["close"]) / 3
    cum_vol = df["volume"].cumsum()
    cum_tpv = (typical * df["volume"]).cumsum()
    return cum_tpv / cum_vol.replace(0, np.nan)


def zscore(series: pd.Series, period: int = 20) -> pd.Series:
    mean = series.rolling(period).mean()
    std  = series.rolling(period).std()
    return (series - mean) / std.replace(0, np.nan)


def compute_all(df: pd.DataFrame) -> dict:
    """Return dict of all indicator series for the given OHLCV dataframe."""
    return {
        "sma20":    sma(df, 20),
        "sma50":    sma(df, 50),
        "ema9":     ema(df, 9),
        "ema21":    ema(df, 21),
        "vwap":     vwap(df),
        "atr14":    atr(df, 14),
        "rsi14":    rsi(df, 14),
        "bb_mid":   bollinger(df)[0],
        "bb_upper": bollinger(df)[1],
        "bb_lower": bollinger(df)[2],
    }
