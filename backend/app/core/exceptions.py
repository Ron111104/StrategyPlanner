"""Custom exception hierarchy for ZQ Strategy Planning Platform.

All platform exceptions inherit from StrategyPlannerError.
Each exception carries structured attributes for logging and API responses.
"""

from __future__ import annotations


class StrategyPlannerError(Exception):
    """Base exception for all Strategy Planner errors.

    Attributes:
        message: Human-readable error description.
        error_code: Machine-readable error code for API responses.
        details: Optional dictionary of additional error context.
    """

    def __init__(
        self,
        message: str = "An unexpected error occurred",
        *,
        error_code: str = "STRATEGY_PLANNER_ERROR",
        details: dict[str, object] | None = None,
    ) -> None:
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"error_code={self.error_code!r}, "
            f"details={self.details!r})"
        )


class InsufficientDataError(StrategyPlannerError):
    """Raised when there is not enough data for a calculation.

    Attributes:
        required: Minimum number of data points required.
        actual: Actual number of data points available.
        context: What operation needed the data.
    """

    def __init__(
        self,
        message: str = "Insufficient data for calculation",
        *,
        required: int = 0,
        actual: int = 0,
        context: str = "",
    ) -> None:
        self.required = required
        self.actual = actual
        self.context = context
        super().__init__(
            message,
            error_code="INSUFFICIENT_DATA",
            details={"required": required, "actual": actual, "context": context},
        )


class InvalidContractError(StrategyPlannerError):
    """Raised when a contract symbol is not found or invalid.

    Attributes:
        symbol: The invalid contract symbol.
    """

    def __init__(
        self,
        message: str = "Invalid contract symbol",
        *,
        symbol: str = "",
    ) -> None:
        self.symbol = symbol
        super().__init__(
            message,
            error_code="INVALID_CONTRACT",
            details={"symbol": symbol},
        )


class RegimeNotSetError(StrategyPlannerError):
    """Raised when a regime state is required but has not been set.

    Attributes:
        product: The product for which regime is missing.
    """

    def __init__(
        self,
        message: str = "Market regime has not been set",
        *,
        product: str = "",
    ) -> None:
        self.product = product
        super().__init__(
            message,
            error_code="REGIME_NOT_SET",
            details={"product": product},
        )


class DataFetchError(StrategyPlannerError):
    """Raised when external data fetching fails.

    Attributes:
        source: The data source that failed.
        status_code: HTTP status code if applicable.
        url: The URL that was being fetched.
    """

    def __init__(
        self,
        message: str = "Failed to fetch external data",
        *,
        source: str = "",
        status_code: int | None = None,
        url: str = "",
    ) -> None:
        self.source = source
        self.status_code = status_code
        self.url = url
        super().__init__(
            message,
            error_code="DATA_FETCH_ERROR",
            details={"source": source, "status_code": status_code, "url": url},
        )


class ConfigurationError(StrategyPlannerError):
    """Raised when configuration is invalid or missing.

    Attributes:
        config_key: The configuration key that is problematic.
        config_file: The configuration file path if applicable.
    """

    def __init__(
        self,
        message: str = "Configuration error",
        *,
        config_key: str = "",
        config_file: str = "",
    ) -> None:
        self.config_key = config_key
        self.config_file = config_file
        super().__init__(
            message,
            error_code="CONFIGURATION_ERROR",
            details={"config_key": config_key, "config_file": config_file},
        )


class ValidationError(StrategyPlannerError):
    """Raised when input validation fails outside of Pydantic.

    Attributes:
        field: The field that failed validation.
        value: The invalid value.
        constraint: Description of the validation constraint.
    """

    def __init__(
        self,
        message: str = "Validation error",
        *,
        field: str = "",
        value: object = None,
        constraint: str = "",
    ) -> None:
        self.field = field
        self.value = value
        self.constraint = constraint
        super().__init__(
            message,
            error_code="VALIDATION_ERROR",
            details={"field": field, "value": str(value), "constraint": constraint},
        )


class IndicatorError(StrategyPlannerError):
    """Raised when indicator calculation fails.

    Attributes:
        indicator_name: Name of the indicator that failed.
        reason: Reason for the failure.
    """

    def __init__(
        self,
        message: str = "Indicator calculation error",
        *,
        indicator_name: str = "",
        reason: str = "",
    ) -> None:
        self.indicator_name = indicator_name
        self.reason = reason
        super().__init__(
            message,
            error_code="INDICATOR_ERROR",
            details={"indicator_name": indicator_name, "reason": reason},
        )
