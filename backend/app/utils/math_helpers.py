"""Math helper functions for ZQ Strategy Planning Platform.

Pure, stateless mathematical utility functions used across
indicator calculations, risk computations, and price operations.
"""

from __future__ import annotations

import math


def round_to_tick(price: float, tick_size: float) -> float:
    """Round a price to the nearest valid tick increment.

    Args:
        price: The raw price to round.
        tick_size: The minimum price increment (e.g. 0.005 for ZQ).

    Returns:
        Price rounded to the nearest tick_size.

    Raises:
        ValueError: If tick_size is not positive.
    """
    if tick_size <= 0:
        raise ValueError(f"tick_size must be positive, got {tick_size}")
    # Use Decimal-safe rounding via multiplication
    ticks = round(price / tick_size)
    result = ticks * tick_size
    # Round to avoid floating-point drift
    decimals = max(0, -int(math.floor(math.log10(tick_size))))
    return round(result, decimals)


def ticks_between(price1: float, price2: float, tick_size: float) -> int:
    """Calculate the number of ticks between two prices.

    Returns the absolute number of ticks between price1 and price2.

    Args:
        price1: First price.
        price2: Second price.
        tick_size: Minimum price increment.

    Returns:
        Absolute integer number of ticks between the two prices.

    Raises:
        ValueError: If tick_size is not positive.
    """
    if tick_size <= 0:
        raise ValueError(f"tick_size must be positive, got {tick_size}")
    return abs(round((price1 - price2) / tick_size))


def dollar_value_of_ticks(ticks: int, tick_value: float) -> float:
    """Calculate the dollar value of a given number of ticks.

    Args:
        ticks: Number of ticks.
        tick_value: Dollar value per tick (e.g. $20.835 for ZQ).

    Returns:
        Dollar value as float.
    """
    return round(abs(ticks) * tick_value, 2)


def percentage_change(old: float, new: float) -> float:
    """Calculate percentage change from old to new value.

    Args:
        old: Original value.
        new: New value.

    Returns:
        Percentage change as a float (e.g. 5.0 for 5%).
        Returns 0.0 if old is zero.
    """
    if old == 0.0:
        return 0.0
    return round(((new - old) / abs(old)) * 100.0, 6)


def wilder_smooth(values: list[float], period: int) -> list[float]:
    """Apply Wilder's smoothing method to a series of values.

    Wilder's smoothing (used in ATR, RSI, etc.) uses:
        smoothed[0] = SMA of first `period` values
        smoothed[i] = (smoothed[i-1] * (period - 1) + values[i]) / period

    Args:
        values: Input series of float values.
        period: Smoothing period (lookback window).

    Returns:
        List of smoothed values. The output length equals
        len(values) - period + 1 (first valid output aligns with
        index period-1 of the original series).

    Raises:
        ValueError: If period < 1 or values has fewer than period elements.
    """
    if period < 1:
        raise ValueError(f"period must be >= 1, got {period}")
    if len(values) < period:
        raise ValueError(
            f"Need at least {period} values for period={period}, got {len(values)}"
        )

    # First smoothed value = simple average of the first `period` values
    initial_avg = sum(values[:period]) / period
    result: list[float] = [round(initial_avg, 10)]

    # Subsequent values use Wilder's recursive formula
    for i in range(period, len(values)):
        smoothed = (result[-1] * (period - 1) + values[i]) / period
        result.append(round(smoothed, 10))

    return result


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default if denominator is zero.

    Args:
        numerator: The dividend.
        denominator: The divisor.
        default: Value to return if denominator is zero.

    Returns:
        Result of division or default value.
    """
    if denominator == 0.0:
        return default
    return numerator / denominator
