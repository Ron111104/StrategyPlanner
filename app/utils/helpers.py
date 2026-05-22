"""General-purpose utility functions."""
from typing import Union


def spread_bp_from_prices(front_price: float, back_price: float) -> float:
    """Compute calendar spread in basis points: (front - back) * 100."""
    return round((front_price - back_price) * 100, 2)


def ticks_between(price_a: float, price_b: float, tick_size: float) -> float:
    """Return number of ticks between two prices."""
    if tick_size <= 0:
        return 0.0
    return round(abs(price_a - price_b) / tick_size, 4)


def format_price(value: float, decimals: int = 4) -> str:
    """Format a price value for display."""
    return f"{value:.{decimals}f}"


def format_bp(value: float) -> str:
    """Format a basis-point value for display."""
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f} bp"


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp a value between minimum and maximum."""
    return max(minimum, min(value, maximum))


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division returning default on zero denominator."""
    if denominator == 0:
        return default
    return numerator / denominator


def pct_change(current: float, previous: float) -> float:
    """Compute percentage change."""
    if previous == 0:
        return 0.0
    return round((current - previous) / abs(previous) * 100, 4)
