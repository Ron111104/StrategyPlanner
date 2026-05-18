"""
Application settings — environment-based configuration management.

All external configuration is loaded from environment variables.
YAML configs are loaded from the config/ directory.
NO hardcoded URLs, tokens, or secrets.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings

# ── Paths ─────────────────────────────────────────────────────
_CONFIG_DIR = Path(__file__).parent
_PROJECT_ROOT = _CONFIG_DIR.parent


class QHApiSettings(BaseSettings):
    """Quant Hub external API settings from environment."""

    base_url: str = Field(default="", alias="QH_API_BASE_URL")
    ohlc_endpoint: str = Field(default="/api/ohlc/", alias="QH_OHLC_ENDPOINT")
    api_token: str = Field(default="", alias="QH_API_TOKEN")
    timeout_seconds: int = Field(default=30, alias="QH_TIMEOUT_SECONDS")

    model_config = {"env_prefix": "", "extra": "ignore"}


class AppSettings(BaseSettings):
    """Global application settings."""

    app_name: str = "ZQ Strategy Planner"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, alias="DEBUG")
    host: str = Field(default="0.0.0.0", alias="APP_HOST")
    port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    cors_origins: str = Field(default="http://localhost:3000,http://localhost:5173", alias="CORS_ORIGINS")

    model_config = {"env_prefix": "", "extra": "ignore"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


# ── YAML Loaders ──────────────────────────────────────────────

def _load_yaml(filename: str) -> dict[str, Any]:
    """Load a YAML configuration file from the config directory."""
    filepath = _CONFIG_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Configuration file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML structure in {filepath}")
    return data


@lru_cache(maxsize=1)
def load_contracts_config() -> dict[str, Any]:
    """Load the contracts configuration."""
    return _load_yaml("contracts.yaml")


@lru_cache(maxsize=1)
def load_strategy_settings() -> dict[str, Any]:
    """Load the strategy settings configuration."""
    return _load_yaml("strategy_settings.yaml")


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    """Get cached application settings."""
    return AppSettings()


@lru_cache(maxsize=1)
def get_qh_settings() -> QHApiSettings:
    """Get cached QH API settings."""
    return QHApiSettings()
