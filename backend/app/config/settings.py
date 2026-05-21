"""Application settings and contract configuration loader.

Uses pydantic-settings for environment-variable-driven configuration
and PyYAML for loading contract/strategy YAML configs into typed models.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve the config directory relative to this file
_CONFIG_DIR = Path(__file__).parent


# ─── Typed configuration models for contracts.yaml ──────────────────────────


class OutrightConfig(BaseModel):
    """Configuration for a single outright Fed Funds futures contract."""

    model_config = {"frozen": True}

    symbol: Annotated[str, Field(min_length=1, description="Contract symbol e.g. FFN25")]
    name: Annotated[str, Field(min_length=1, description="Human-readable name")]
    expiry: date
    tick_size: Annotated[float, Field(gt=0)]
    tick_value: Annotated[float, Field(gt=0)]
    contract_value: Annotated[float, Field(gt=0)]
    point_value: Annotated[float, Field(gt=0)]


class SpreadConfig(BaseModel):
    """Configuration for a calendar spread between two outright contracts."""

    model_config = {"frozen": True}

    symbol: Annotated[str, Field(min_length=1, description="Spread symbol e.g. FFN25-FFQ25")]
    name: Annotated[str, Field(min_length=1, description="Human-readable name")]
    front_contract: Annotated[str, Field(min_length=1, description="Front leg symbol")]
    back_contract: Annotated[str, Field(min_length=1, description="Back leg symbol")]
    tick_size_bp: Annotated[float, Field(gt=0, description="Tick size in basis points")]
    tick_value: Annotated[float, Field(gt=0, description="Dollar value per tick")]


class ContractRegistry(BaseModel):
    """Registry of all configured outright and spread contracts.

    Provides lookup methods by symbol.
    """

    outrights: list[OutrightConfig] = Field(default_factory=list)
    spreads: list[SpreadConfig] = Field(default_factory=list)

    def get_outright(self, symbol: str) -> OutrightConfig | None:
        """Look up an outright contract by symbol.

        Args:
            symbol: Contract symbol (case-sensitive).

        Returns:
            OutrightConfig if found, None otherwise.
        """
        for contract in self.outrights:
            if contract.symbol == symbol:
                return contract
        return None

    def get_spread(self, symbol: str) -> SpreadConfig | None:
        """Look up a spread contract by symbol.

        Args:
            symbol: Spread symbol (case-sensitive).

        Returns:
            SpreadConfig if found, None otherwise.
        """
        for spread in self.spreads:
            if spread.symbol == symbol:
                return spread
        return None

    def get_contract(self, symbol: str) -> OutrightConfig | SpreadConfig | None:
        """Look up any contract (outright or spread) by symbol.

        Args:
            symbol: Contract or spread symbol.

        Returns:
            OutrightConfig or SpreadConfig if found, None otherwise.
        """
        return self.get_outright(symbol) or self.get_spread(symbol)

    def all_outright_symbols(self) -> list[str]:
        """Return all outright contract symbols."""
        return [c.symbol for c in self.outrights]

    def all_spread_symbols(self) -> list[str]:
        """Return all spread symbols."""
        return [s.symbol for s in self.spreads]

    def all_symbols(self) -> list[str]:
        """Return all contract and spread symbols."""
        return self.all_outright_symbols() + self.all_spread_symbols()

    def is_spread(self, symbol: str) -> bool:
        """Check if a symbol is a spread."""
        return self.get_spread(symbol) is not None


# ─── Typed configuration models for strategy_settings.yaml ──────────────────


class ATRConfig(BaseModel):
    """ATR indicator settings."""

    model_config = {"frozen": True}
    length: int = 14
    smoothing: str = "wilder"


class MAConfig(BaseModel):
    """Moving average indicator settings."""

    model_config = {"frozen": True}
    lengths: list[int] = Field(default_factory=lambda: [10, 20, 50])


class DonchianConfig(BaseModel):
    """Donchian channel settings."""

    model_config = {"frozen": True}
    length: int = 20


class BollingerConfig(BaseModel):
    """Bollinger band settings."""

    model_config = {"frozen": True}
    length: int = 20
    std_dev: float = 2.0


class DCWConfig(BaseModel):
    """Donchian Channel Width settings."""

    model_config = {"frozen": True}
    length: int = 20


class IndicatorsConfig(BaseModel):
    """All indicator configurations."""

    model_config = {"frozen": True}
    atr: ATRConfig = ATRConfig()
    sma: MAConfig = MAConfig()
    ema: MAConfig = MAConfig(lengths=[9, 21, 50])
    donchian: DonchianConfig = DonchianConfig()
    bollinger: BollingerConfig = BollingerConfig()
    dcw: DCWConfig = DCWConfig()


class StrategyConfig(BaseModel):
    """Strategy engine configuration."""

    model_config = {"frozen": True}
    min_bars_required: int = 51
    confidence_threshold: float = 0.6
    max_simultaneous_signals: int = 5


class RiskConfig(BaseModel):
    """Risk management configuration."""

    model_config = {"frozen": True}
    default_risk_per_trade_usd: float = 500.0
    max_risk_per_trade_usd: float = 2000.0
    default_slippage_ticks: int = 1
    default_commission_per_side: float = 2.50
    event_risk_reduction: float = 0.5
    max_position_size: int = 50
    volatility_sizing_enabled: bool = True


class RegimeConfig(BaseModel):
    """Market regime detection configuration."""

    model_config = {"frozen": True}
    trend_atr_threshold: float = 1.5
    volatility_atr_threshold: float = 2.0
    range_dcw_threshold: float = 0.3
    event_window_hours: float = 4.0
    regime_expiry_hours: float = 24.0


class TimeframesConfig(BaseModel):
    """Allowed timeframe configuration."""

    model_config = {"frozen": True}
    allowed: list[str] = Field(default_factory=lambda: ["1M", "5M", "15M", "1H", "4H", "1D"])
    default: str = "1H"


class ReplayConfig(BaseModel):
    """Replay/simulation configuration."""

    model_config = {"frozen": True}
    default_speed: float = 1.0
    max_speed: float = 10.0
    bar_buffer: int = 100


class StrategySettings(BaseModel):
    """Top-level strategy settings parsed from strategy_settings.yaml."""

    indicators: IndicatorsConfig = IndicatorsConfig()
    strategy: StrategyConfig = StrategyConfig()
    risk: RiskConfig = RiskConfig()
    regime: RegimeConfig = RegimeConfig()
    timeframes: TimeframesConfig = TimeframesConfig()
    replay: ReplayConfig = ReplayConfig()


# ─── Contract & Strategy Loader ─────────────────────────────────────────────


class ContractLoader:
    """Loads and parses YAML configuration files into typed models.

    Reads contracts.yaml and strategy_settings.yaml from the config directory
    and returns fully validated Pydantic model instances.
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        """Initialize the loader with an optional config directory override.

        Args:
            config_dir: Path to the directory containing YAML configs.
                        Defaults to the directory containing this file.
        """
        self._config_dir = config_dir or _CONFIG_DIR

    def _load_yaml(self, filename: str) -> dict[str, Any]:
        """Load and parse a YAML file.

        Args:
            filename: Name of the YAML file to load.

        Returns:
            Parsed YAML content as a dictionary.

        Raises:
            FileNotFoundError: If the YAML file does not exist.
            yaml.YAMLError: If the YAML file is malformed.
        """
        filepath = self._config_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Configuration file not found: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Expected a YAML mapping in {filepath}, got {type(data).__name__}")
        return data

    def load_contract_registry(self) -> ContractRegistry:
        """Load contracts.yaml and return a ContractRegistry.

        Returns:
            A fully validated ContractRegistry instance.
        """
        data = self._load_yaml("contracts.yaml")
        contracts_data = data.get("contracts", {})

        outrights_raw = contracts_data.get("outrights", [])
        spreads_raw = contracts_data.get("spreads", [])

        outrights = [OutrightConfig(**item) for item in outrights_raw]
        spreads = [SpreadConfig(**item) for item in spreads_raw]

        return ContractRegistry(outrights=outrights, spreads=spreads)

    def load_strategy_settings(self) -> StrategySettings:
        """Load strategy_settings.yaml and return StrategySettings.

        Returns:
            A fully validated StrategySettings instance.
        """
        data = self._load_yaml("strategy_settings.yaml")
        return StrategySettings(**data)


# ─── Application Settings (env-driven) ──────────────────────────────────────


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables.

    Supports .env files and direct environment variable overrides.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "ZQ Strategy Planner"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # External Market Data
    market_data_api_url: str = "https://api.example.com"
    market_data_api_key: str = ""

    # Redis (optional)
    redis_url: str | None = None

    # CORS
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"])

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure log_level is a valid Python logging level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid_levels:
            raise ValueError(f"Invalid log_level: {v!r}. Must be one of {valid_levels}")
        return upper

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        if isinstance(v, list):
            return v
        raise ValueError(f"cors_origins must be a string or list, got {type(v).__name__}")


# ─── Cached singletons ──────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()


@lru_cache(maxsize=1)
def get_contract_registry() -> ContractRegistry:
    """Return the cached contract registry singleton."""
    loader = ContractLoader()
    return loader.load_contract_registry()


@lru_cache(maxsize=1)
def get_strategy_settings() -> StrategySettings:
    """Return the cached strategy settings singleton."""
    loader = ContractLoader()
    return loader.load_strategy_settings()
