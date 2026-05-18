"""
Math utility helpers — tick conversions, rounding, and general computations.
"""

from __future__ import annotations

import math
from typing import Optional


def round_to_tick(price: float, tick_size: float) -> float:
    """Round a price to the nearest valid tick increment."""
    if tick_size <= 0:
        raise ValueError(f"tick_size must be positive, got {tick_size}")
    return round(round(price / tick_size) * tick_size, 10)


def price_to_ticks(price_distance: float, tick_size: float) -> float:
    """Convert a price distance to number of ticks."""
    if tick_size <= 0:
        raise ValueError(f"tick_size must be positive, got {tick_size}")
    return abs(price_distance) / tick_size


def ticks_to_price(num_ticks: float, tick_size: float) -> float:
    """Convert number of ticks to price distance."""
    return num_ticks * tick_size


def ticks_to_dollars(num_ticks: float, tick_value: float) -> float:
    """Convert number of ticks to dollar value."""
    return num_ticks * tick_value


def dollars_to_ticks(dollars: float, tick_value: float) -> float:
    """Convert dollar value to number of ticks."""
    if tick_value <= 0:
        raise ValueError(f"tick_value must be positive, got {tick_value}")
    return dollars / tick_value


def compute_max_lots(
    max_risk_usd: float,
    stop_ticks: float,
    tick_value: float,
) -> int:
    """
    Position sizing formula:
    max_lots = floor(max_risk_usd / (stop_ticks * tick_value))
    """
    if stop_ticks <= 0 or tick_value <= 0:
        return 0
    raw = max_risk_usd / (stop_ticks * tick_value)
    return max(0, math.floor(raw))


def compute_rr_ratio(
    entry: float,
    stop: float,
    target: float,
) -> Optional[float]:
    """Compute risk/reward ratio. Returns None if stop == entry."""
    risk = abs(entry - stop)
    if risk == 0:
        return None
    reward = abs(target - entry)
    return round(reward / risk, 2)


def percentile(values: list[float], pct: float) -> float:
    """Compute percentile of a sorted list."""
    if not values:
        raise ValueError("Cannot compute percentile of empty list")
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return d0 + d1


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division with default for zero denominator."""
    if denominator == 0:
        return default
    return numerator / denominator
