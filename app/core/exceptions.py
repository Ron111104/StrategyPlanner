"""Application-level exception definitions."""
from typing import Any


class StrategyPlannerError(Exception):
    """Base exception for the platform."""

    def __init__(self, message: str, detail: Any = None) -> None:
        self.message = message
        self.detail = detail
        super().__init__(self.message)


class ConfigurationError(StrategyPlannerError):
    """Raised when configuration is invalid or missing."""


class ContractNotFoundError(StrategyPlannerError):
    """Raised when a requested contract is not in configuration."""


class ProductNotFoundError(StrategyPlannerError):
    """Raised when a requested product is not in configuration."""


class MarketDataError(StrategyPlannerError):
    """Raised when market data fetch or processing fails."""


class InsufficientDataError(StrategyPlannerError):
    """Raised when there are not enough bars for calculation."""


class IndicatorError(StrategyPlannerError):
    """Raised when indicator computation fails."""


class StrategyError(StrategyPlannerError):
    """Raised when strategy evaluation fails."""


class RiskError(StrategyPlannerError):
    """Raised when risk calculation fails."""


class AdapterError(StrategyPlannerError):
    """Raised when an external adapter call fails."""
