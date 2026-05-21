"""Spread calculation helper functions for ZQ Strategy Planning Platform.

Pure, stateless functions for Fed Funds spread computations,
implied rate conversions, and basis point calculations.
"""

from __future__ import annotations


def price_to_spread_bp(front_price: float, back_price: float) -> float:
    """Convert front and back contract prices to spread in basis points.

    For Fed Funds Futures, spread = (front_price - back_price) * 100 basis points.

    Args:
        front_price: Front (nearer expiry) contract price.
        back_price: Back (farther expiry) contract price.

    Returns:
        Spread in basis points, rounded to 4 decimal places.
    """
    return round((front_price - back_price) * 100, 4)


def spread_bp_to_ticks(spread_bp: float, tick_size_bp: float) -> float:
    """Convert a spread in basis points to a number of ticks.

    Args:
        spread_bp: Spread value in basis points.
        tick_size_bp: Tick size in basis points (e.g. 0.5 for ZQ spreads).

    Returns:
        Number of ticks as a float.

    Raises:
        ValueError: If tick_size_bp is not positive.
    """
    if tick_size_bp <= 0:
        raise ValueError(f"tick_size_bp must be positive, got {tick_size_bp}")
    return round(spread_bp / tick_size_bp, 6)


def spread_ticks_to_dollar(ticks: float, tick_value: float) -> float:
    """Convert spread ticks to dollar value.

    Args:
        ticks: Number of ticks (can be fractional).
        tick_value: Dollar value per tick.

    Returns:
        Dollar value, rounded to 2 decimal places.
    """
    return round(abs(ticks) * tick_value, 2)


def implied_rate_from_price(price: float) -> float:
    """Calculate the implied Fed Funds rate from a futures price.

    Fed Funds Futures are quoted as 100 - rate. So:
        implied_rate = 100.0 - price

    Args:
        price: Futures price (e.g. 95.755 implies 4.245% rate).

    Returns:
        Implied rate as a float (e.g. 4.245).
    """
    return round(100.0 - price, 6)


def price_from_implied_rate(rate: float) -> float:
    """Calculate the futures price from an implied Fed Funds rate.

    Args:
        rate: Implied rate (e.g. 4.245%).

    Returns:
        Futures price (e.g. 95.755).
    """
    return round(100.0 - rate, 6)


def rate_change_bp(old_price: float, new_price: float) -> float:
    """Calculate the change in implied rate between two prices in basis points.

    Since rate = 100 - price, a price decrease = rate increase.
    rate_change = (old_price - new_price) * 100 basis points.

    Args:
        old_price: Previous futures price.
        new_price: Current futures price.

    Returns:
        Rate change in basis points. Positive means rates rose (price fell).
    """
    old_rate = implied_rate_from_price(old_price)
    new_rate = implied_rate_from_price(new_price)
    return round((new_rate - old_rate) * 100, 4)
