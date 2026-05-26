"""QH API client — OHLCV + VAP fetch with parquet caching."""

import os, json, hashlib, time
from pathlib import Path
from typing import Optional
import httpx
import pandas as pd
import numpy as np
from dotenv import load_dotenv

load_dotenv()
BASE_URL = os.getenv("QH_BASE_URL", "").rstrip("/")
TOKEN    = os.getenv("QH_TOKEN", "")
CACHE    = Path("data_cache")
CACHE.mkdir(exist_ok=True)
CACHE_TTL = 300  # seconds


def _headers():
    return {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}


def _cache_path(key: str) -> Path:
    h = hashlib.md5(key.encode()).hexdigest()[:12]
    return CACHE / f"{h}.parquet"


def _is_fresh(p: Path) -> bool:
    return p.exists() and (time.time() - p.stat().st_mtime) < CACHE_TTL


# ---------------------------------------------------------------------------
# OHLCV
# ---------------------------------------------------------------------------

def fetch_ohlcv(product: str, interval: str = "1D") -> pd.DataFrame:
    """Fetch OHLCV from QH or cache. Returns DataFrame with datetime index."""
    cache_key = f"ohlcv_{product}_{interval}"
    cp = _cache_path(cache_key)
    if _is_fresh(cp):
        return pd.read_parquet(cp)

    url = f"{BASE_URL}/api/ohlc/?products={product}&timeIntervals={interval}"
    try:
        r = httpx.get(url, headers=_headers(), timeout=15)
        r.raise_for_status()
        raw = r.json()
    except Exception as e:
        if cp.exists():
            return pd.read_parquet(cp)  # stale fallback
        raise RuntimeError(f"QH OHLCV fetch failed: {e}")

    key = f"{product}_{interval}"
    payload = raw.get(key, {})
    cols = payload.get("columns", [])
    data = payload.get("DATA", [])

    if not data:
        raise RuntimeError(f"No OHLCV data for {product}/{interval}")

    df = pd.DataFrame(data, columns=cols)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="s", utc=True)
    df = df.set_index("Timestamp").sort_index()
    df.columns = [c.lower() for c in df.columns]
    df = df.astype(float)
    df.to_parquet(cp)
    return df


# ---------------------------------------------------------------------------
# VAP
# ---------------------------------------------------------------------------

def _parse_vap_string(vap_str: str) -> list[dict]:
    """Parse 'price:buyVol-sellVol;...' into list of dicts."""
    entries = []
    for chunk in vap_str.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            price_part, vol_part = chunk.split(":")
            buy_str, sell_str = vol_part.split("-")
            entries.append({
                "price": float(price_part),
                "buy_vol": int(buy_str),
                "sell_vol": int(sell_str),
                "total_vol": int(buy_str) + int(sell_str),
            })
        except Exception:
            continue
    return entries


def fetch_vap(product: str, interval: str = "1D", count: int = 500) -> pd.DataFrame:
    """Fetch VAP and return flat DataFrame: time, price, buy_vol, sell_vol, total_vol."""
    cache_key = f"vap_{product}_{interval}_{count}"
    cp = _cache_path(cache_key)
    if _is_fresh(cp):
        return pd.read_parquet(cp)

    url = f"{BASE_URL}/api/v2/vap/?instruments={product}&interval={interval}&count={count}"
    try:
        r = httpx.get(url, headers=_headers(), timeout=15)
        r.raise_for_status()
        raw = r.json()
    except Exception as e:
        if cp.exists():
            return pd.read_parquet(cp)
        raise RuntimeError(f"QH VAP fetch failed: {e}")

    rows = []
    for record in raw:
        ts = pd.to_datetime(record["time"], unit="ms", utc=True)
        for entry in _parse_vap_string(record.get("vap", "")):
            entry["time"] = ts
            rows.append(entry)

    if not rows:
        return pd.DataFrame(columns=["time", "price", "buy_vol", "sell_vol", "total_vol"])

    df = pd.DataFrame(rows)
    df = df.set_index("time").sort_index()
    df.to_parquet(cp)
    return df


# ---------------------------------------------------------------------------
# VAP aggregation helpers
# ---------------------------------------------------------------------------

def vap_poc(vap_df: pd.DataFrame) -> float:
    """Point of Control — price with highest total volume."""
    if vap_df.empty:
        return float("nan")
    return float(vap_df.groupby("price")["total_vol"].sum().idxmax())


def vap_value_area(vap_df: pd.DataFrame, pct: float = 0.70):
    """Return (VAL, VAH) value area covering pct of total volume."""
    if vap_df.empty:
        return float("nan"), float("nan")
    grouped = vap_df.groupby("price")["total_vol"].sum().sort_index()
    total = grouped.sum()
    target = total * pct
    poc_price = grouped.idxmax()
    poc_idx = list(grouped.index).index(poc_price)
    lo = hi = poc_idx
    covered = grouped.iloc[poc_idx]
    while covered < target and (lo > 0 or hi < len(grouped) - 1):
        lo_vol = grouped.iloc[lo - 1] if lo > 0 else 0
        hi_vol = grouped.iloc[hi + 1] if hi < len(grouped) - 1 else 0
        if lo_vol >= hi_vol and lo > 0:
            lo -= 1; covered += lo_vol
        elif hi < len(grouped) - 1:
            hi += 1; covered += hi_vol
        else:
            lo -= 1; covered += lo_vol
    return float(grouped.index[lo]), float(grouped.index[hi])


def vap_imbalance(vap_df: pd.DataFrame, last_n_bars: int = 5) -> float:
    """Buy/sell imbalance score -1 to +1 for recent N bars."""
    if vap_df.empty:
        return 0.0
    recent = vap_df.tail(last_n_bars * 50)  # rough approx
    buy = recent["buy_vol"].sum()
    sell = recent["sell_vol"].sum()
    total = buy + sell
    if total == 0:
        return 0.0
    return float((buy - sell) / total)


# ---------------------------------------------------------------------------
# Resampling for synthetic timeframes
# ---------------------------------------------------------------------------

RESAMPLE_MAP = {
    "15M": "15min",
    "1H":  "1h",
    "4H":  "4h",
}


def resample_ohlcv(df_5m: pd.DataFrame, target_tf: str) -> pd.DataFrame:
    """Resample 5M OHLCV to 15M / 1H / 4H."""
    rule = RESAMPLE_MAP.get(target_tf)
    if rule is None:
        return df_5m
    agg = {
        "open":   "first",
        "high":   "max",
        "low":    "min",
        "close":  "last",
        "volume": "sum",
    }
    return df_5m.resample(rule).agg(agg).dropna()


def get_ohlcv(product: str, timeframe: str) -> pd.DataFrame:
    """Smart fetch: use 5M as base for synthetic TFs, 1D direct."""
    if timeframe == "1D":
        return fetch_ohlcv(product, "1D")
    elif timeframe == "5M":
        return fetch_ohlcv(product, "5M")
    else:
        df5 = fetch_ohlcv(product, "5M")
        return resample_ohlcv(df5, timeframe)


# ---------------------------------------------------------------------------
# Spread construction
# ---------------------------------------------------------------------------

def build_spread(leg1: str, leg2: str, timeframe: str) -> pd.DataFrame:
    """Synthetic spread series: leg1.close - leg2.close."""
    d1 = get_ohlcv(leg1, timeframe)
    d2 = get_ohlcv(leg2, timeframe)
    combined = d1[["open","high","low","close","volume"]].copy()
    d2_close = d2["close"].reindex(combined.index, method="ffill")
    # Build spread OHLC approximately
    spread_close = combined["close"] - d2_close
    spread_open  = combined["open"] - d2["open"].reindex(combined.index, method="ffill")
    spread_high  = combined["high"] - d2["low"].reindex(combined.index, method="ffill")
    spread_low   = combined["low"] - d2["high"].reindex(combined.index, method="ffill")
    out = pd.DataFrame({
        "open":   spread_open,
        "high":   spread_high,
        "low":    spread_low,
        "close":  spread_close,
        "volume": combined["volume"],
    }).dropna()
    return out
