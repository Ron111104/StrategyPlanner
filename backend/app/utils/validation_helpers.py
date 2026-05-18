"""
Data validation helpers — bar validation, candle integrity, series checks.
"""

from __future__ import annotations

from datetime import datetime

from app.contracts.market_data import OHLCVBar
from app.utils.datetime_helpers import bars_are_monotonic, find_duplicate_timestamps


class ValidationError(Exception):
    """Custom validation error for market data."""

    def __init__(self, message: str, field: str = "", details: dict | None = None):
        self.message = message
        self.field = field
        self.details = details or {}
        super().__init__(message)


class ValidationWarning:
    """Non-fatal validation warning."""

    def __init__(self, message: str, field: str = ""):
        self.message = message
        self.field = field


def validate_ohlcv_bar(bar: OHLCVBar) -> list[ValidationWarning]:
    """
    Validate a single OHLCV bar for structural integrity.

    Raises ValidationError for fatal issues.
    Returns list of warnings for non-fatal issues.
    """
    warnings: list[ValidationWarning] = []

    # Fatal checks
    if bar.high < bar.low:
        raise ValidationError(
            f"Invalid OHLC: high ({bar.high}) < low ({bar.low})",
            field="high/low",
            details={"product": bar.product, "timestamp": str(bar.timestamp)},
        )

    if bar.high < bar.open or bar.high < bar.close:
        raise ValidationError(
            f"Invalid OHLC: high ({bar.high}) < open ({bar.open}) or close ({bar.close})",
            field="high",
            details={"product": bar.product, "timestamp": str(bar.timestamp)},
        )

    if bar.low > bar.open or bar.low > bar.close:
        raise ValidationError(
            f"Invalid OHLC: low ({bar.low}) > open ({bar.open}) or close ({bar.close})",
            field="low",
            details={"product": bar.product, "timestamp": str(bar.timestamp)},
        )

    # Warning checks
    if bar.volume == 0:
        warnings.append(ValidationWarning(
            f"Zero volume for {bar.product} at {bar.timestamp}",
            field="volume",
        ))

    bar_range = bar.high - bar.low
    if bar_range == 0:
        warnings.append(ValidationWarning(
            f"Zero range (doji) for {bar.product} at {bar.timestamp}",
            field="range",
        ))

    return warnings


def validate_bar_series(
    bars: list[OHLCVBar],
    min_bars: int = 51,
) -> tuple[list[ValidationWarning], list[ValidationError]]:
    """
    Validate a series of OHLCV bars.

    Returns (warnings, errors).
    """
    warnings: list[ValidationWarning] = []
    errors: list[ValidationError] = []

    if len(bars) < min_bars:
        errors.append(ValidationError(
            f"Insufficient bars: {len(bars)} < {min_bars} minimum required",
            field="bar_count",
        ))
        return warnings, errors

    # Check monotonicity
    timestamps = [bar.timestamp for bar in bars]
    if not bars_are_monotonic(timestamps):
        errors.append(ValidationError(
            "Non-monotonic timestamps detected",
            field="timestamps",
        ))

    # Check duplicates
    duplicates = find_duplicate_timestamps(timestamps)
    if duplicates:
        errors.append(ValidationError(
            f"Duplicate timestamps found: {len(duplicates)}",
            field="timestamps",
            details={"duplicates": [str(d) for d in duplicates[:5]]},
        ))

    # Validate each bar
    for bar in bars:
        try:
            bar_warnings = validate_ohlcv_bar(bar)
            warnings.extend(bar_warnings)
        except ValidationError as e:
            errors.append(e)

    return warnings, errors


def validate_product_match(bars: list[OHLCVBar], expected_product: str) -> None:
    """Ensure all bars belong to the expected product."""
    mismatched = [b for b in bars if b.product != expected_product]
    if mismatched:
        raise ValidationError(
            f"Product mismatch: expected {expected_product}, found {set(b.product for b in mismatched)}",
            field="product",
        )
