"""Datetime helper functions for ZQ Strategy Planning Platform.

Utility functions for timestamp parsing, timezone handling,
timeframe conversion, and event window calculations.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def now_utc() -> datetime:
    """Return the current UTC datetime (timezone-aware).

    Returns:
        Current datetime with UTC timezone info.
    """
    return datetime.now(UTC)


def parse_timestamp(ts: str | int | float) -> datetime:
    """Parse a timestamp from various formats into a UTC-aware datetime.

    Supports:
        - ISO 8601 strings (with or without timezone)
        - Unix timestamps as int or float (seconds since epoch)

    Args:
        ts: Timestamp as ISO string, Unix int, or Unix float.

    Returns:
        Timezone-aware UTC datetime.

    Raises:
        ValueError: If the timestamp format cannot be parsed.
    """
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=UTC)

    if isinstance(ts, str):
        # Try ISO 8601 parsing first
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            pass

        # Try parsing as a numeric string (Unix timestamp)
        try:
            numeric_ts = float(ts)
            return datetime.fromtimestamp(numeric_ts, tz=UTC)
        except (ValueError, OverflowError, OSError):
            pass

        raise ValueError(f"Unable to parse timestamp: {ts!r}")

    raise ValueError(f"Unsupported timestamp type: {type(ts).__name__}")


_TIMEFRAME_SECONDS: dict[str, int] = {
    "1M": 60,
    "5M": 300,
    "15M": 900,
    "1H": 3600,
    "4H": 14400,
    "1D": 86400,
}


def timeframe_to_seconds(tf: str) -> int:
    """Convert a timeframe string to its duration in seconds.

    Args:
        tf: Timeframe string (e.g. '1M', '5M', '15M', '1H', '4H', '1D').

    Returns:
        Duration in seconds.

    Raises:
        ValueError: If the timeframe is not recognized.
    """
    tf_upper = tf.upper()
    if tf_upper not in _TIMEFRAME_SECONDS:
        raise ValueError(
            f"Unknown timeframe: {tf!r}. "
            f"Supported: {', '.join(sorted(_TIMEFRAME_SECONDS.keys()))}"
        )
    return _TIMEFRAME_SECONDS[tf_upper]


def is_within_event_window(
    event_time: datetime,
    current_time: datetime,
    window_hours: float,
) -> bool:
    """Check if the current time is within an event window.

    The event window spans from (event_time - window_hours) to
    (event_time + window_hours).

    Args:
        event_time: The scheduled event time.
        current_time: The current time to check.
        window_hours: The half-window size in hours.

    Returns:
        True if current_time is within the event window.
    """
    window = timedelta(hours=window_hours)
    window_start = event_time - window
    window_end = event_time + window
    return window_start <= current_time <= window_end


def format_timestamp(dt: datetime, fmt: str = "%Y-%m-%dT%H:%M:%SZ") -> str:
    """Format a datetime into a string.

    Args:
        dt: Datetime to format.
        fmt: strftime format string.

    Returns:
        Formatted datetime string.
    """
    return dt.strftime(fmt)
