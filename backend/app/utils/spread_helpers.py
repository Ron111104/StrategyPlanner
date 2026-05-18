"""
Spread calculation helpers — basis point conversions and spread math.
"""

from __future__ import annotations

from app.contracts.market_data import OHLCVBar, SpreadBar, Timeframe


def price_to_bp(front_price: float, back_price: float) -> float:
    """
    Convert outright price differential to basis points.

    spread_bp = (front_price - back_price) * 100
    1 full price point = 100 basis points
    """
    return round((front_price - back_price) * 100, 2)


def bp_to_price(spread_bp: float) -> float:
    """Convert basis points back to price differential."""
    return spread_bp / 100.0


def compute_spread_bar(
    front_bar: OHLCVBar,
    back_bar: OHLCVBar,
    spread_symbol: str,
) -> SpreadBar:
    """
    Compute a spread bar from two outright bars.

    All spread values are stored in basis points internally.
    """
    return SpreadBar(
        timestamp=front_bar.timestamp,
        open_bp=price_to_bp(front_bar.open, back_bar.open),
        high_bp=price_to_bp(front_bar.high, back_bar.low),  # max spread
        low_bp=price_to_bp(front_bar.low, back_bar.high),  # min spread
        close_bp=price_to_bp(front_bar.close, back_bar.close),
        volume=min(front_bar.volume, back_bar.volume),
        timeframe=front_bar.timeframe,
        product=spread_symbol,
        front_contract=front_bar.product,
        back_contract=back_bar.product,
    )


def compute_spread_series(
    front_bars: list[OHLCVBar],
    back_bars: list[OHLCVBar],
    spread_symbol: str,
) -> list[SpreadBar]:
    """
    Compute a series of spread bars from aligned outright bar series.

    Both series must have matching timestamps.
    """
    if len(front_bars) != len(back_bars):
        raise ValueError(
            f"Bar count mismatch: front={len(front_bars)}, back={len(back_bars)}"
        )

    spread_bars: list[SpreadBar] = []
    for front, back in zip(front_bars, back_bars):
        if front.timestamp != back.timestamp:
            raise ValueError(
                f"Timestamp mismatch: front={front.timestamp}, back={back.timestamp}"
            )
        spread_bars.append(compute_spread_bar(front, back, spread_symbol))

    return spread_bars


def spread_ticks_bp(spread_bp_distance: float, tick_size_bp: float = 0.5) -> float:
    """Convert a spread basis point distance to number of spread ticks."""
    if tick_size_bp <= 0:
        raise ValueError(f"tick_size_bp must be positive, got {tick_size_bp}")
    return abs(spread_bp_distance) / tick_size_bp
