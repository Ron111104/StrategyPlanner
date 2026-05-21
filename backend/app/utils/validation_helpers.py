"""Validation helper functions for ZQ Strategy Planning Platform.

Reusable validation functions that raise descriptive errors
for common input validation patterns across the platform.
"""

from __future__ import annotations

from typing import Any

_VALID_TIMEFRAMES = {"1M", "5M", "15M", "1H", "4H", "1D"}


def validate_bars_minimum(bars: list[Any], minimum: int, context: str) -> bool:
    """Validate that a list of bars meets the minimum length requirement.

    Args:
        bars: List of bar objects (OHLCVBar or similar).
        minimum: Minimum required number of bars.
        context: Descriptive context for the error message (e.g. 'ATR calculation').

    Returns:
        True if validation passes.

    Raises:
        ValueError: If bars has fewer than minimum elements.
    """
    if len(bars) < minimum:
        raise ValueError(
            f"Insufficient data for {context}: "
            f"need at least {minimum} bars, got {len(bars)}"
        )
    return True


def validate_price_positive(price: float, field_name: str) -> float:
    """Validate that a price value is strictly positive.

    Args:
        price: The price to validate.
        field_name: Name of the field for the error message.

    Returns:
        The validated price.

    Raises:
        ValueError: If price is not positive.
    """
    if price <= 0:
        raise ValueError(f"{field_name} must be positive, got {price}")
    return price


def validate_tick_size(tick_size: float) -> float:
    """Validate that a tick size is a positive number.

    Args:
        tick_size: The tick size to validate.

    Returns:
        The validated tick size.

    Raises:
        ValueError: If tick_size is not positive.
    """
    if tick_size <= 0:
        raise ValueError(f"tick_size must be positive, got {tick_size}")
    return tick_size


def validate_timeframe(tf: str) -> str:
    """Validate that a timeframe string is recognized.

    Args:
        tf: Timeframe string to validate (e.g. '1H', '5M').

    Returns:
        The validated timeframe string (uppercased).

    Raises:
        ValueError: If the timeframe is not in the allowed set.
    """
    tf_upper = tf.upper()
    if tf_upper not in _VALID_TIMEFRAMES:
        raise ValueError(
            f"Invalid timeframe: {tf!r}. "
            f"Allowed: {', '.join(sorted(_VALID_TIMEFRAMES))}"
        )
    return tf_upper
