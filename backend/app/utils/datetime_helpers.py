"""
Datetime utility helpers — timezone handling, bar alignment, staleness checks.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.contracts.market_data import Timeframe


def utc_now() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime is UTC-aware."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_stale(
    timestamp: datetime,
    max_age_minutes: int = 60,
) -> bool:
    """Check if a timestamp is stale beyond max_age_minutes."""
    now = utc_now()
    ts = ensure_utc(timestamp)
    return (now - ts) > timedelta(minutes=max_age_minutes)


def timeframe_to_minutes(tf: Timeframe) -> int:
    """Convert a Timeframe enum to minutes."""
    mapping = {
        Timeframe.M1: 1,
        Timeframe.M5: 5,
        Timeframe.M15: 15,
        Timeframe.H1: 60,
        Timeframe.H4: 240,
        Timeframe.D1: 1440,
    }
    return mapping[tf]


def timeframe_to_timedelta(tf: Timeframe) -> timedelta:
    """Convert a Timeframe enum to timedelta."""
    return timedelta(minutes=timeframe_to_minutes(tf))


def bars_are_monotonic(timestamps: list[datetime]) -> bool:
    """Verify that timestamps are strictly monotonically increasing."""
    for i in range(1, len(timestamps)):
        if timestamps[i] <= timestamps[i - 1]:
            return False
    return True


def find_duplicate_timestamps(timestamps: list[datetime]) -> list[datetime]:
    """Find any duplicate timestamps in a list."""
    seen: set[datetime] = set()
    duplicates: list[datetime] = []
    for ts in timestamps:
        if ts in seen:
            duplicates.append(ts)
        seen.add(ts)
    return duplicates


def hours_until_event(event_time: datetime) -> float:
    """Calculate hours until a scheduled event."""
    now = utc_now()
    event = ensure_utc(event_time)
    delta = event - now
    return delta.total_seconds() / 3600.0


def is_within_event_window(
    event_time: datetime,
    window_hours: float = 4.0,
) -> bool:
    """Check if current time is within the event lock window."""
    hours = hours_until_event(event_time)
    return -window_hours <= hours <= window_hours
