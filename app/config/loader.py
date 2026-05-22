"""YAML configuration loader with validation."""
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.core.exceptions import ConfigurationError
from app.core.settings import get_settings


def _load_yaml(file_path: Path) -> dict[str, Any]:
    """Load and parse a YAML file."""
    if not file_path.exists():
        raise ConfigurationError(f"Configuration file not found: {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            raise ConfigurationError(f"Empty configuration file: {file_path}")
        return data
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in {file_path}: {e}")


@lru_cache(maxsize=1)
def load_contracts_config() -> dict[str, Any]:
    """Load the contracts configuration."""
    config_dir = get_settings().config_dir
    return _load_yaml(config_dir / "contracts.yaml")


@lru_cache(maxsize=1)
def load_strategy_settings() -> dict[str, Any]:
    """Load the strategy settings configuration."""
    config_dir = get_settings().config_dir
    return _load_yaml(config_dir / "strategy_settings.yaml")


def reload_contracts_config() -> dict[str, Any]:
    """Reload contracts config, clearing cache."""
    load_contracts_config.cache_clear()
    return load_contracts_config()


def reload_strategy_settings() -> dict[str, Any]:
    """Reload strategy settings, clearing cache."""
    load_strategy_settings.cache_clear()
    return load_strategy_settings()


def get_product_config(product_key: str) -> dict[str, Any]:
    """Get configuration for a specific product."""
    config = load_contracts_config()
    products = config.get("products", {})
    if product_key not in products:
        raise ConfigurationError(
            f"Product '{product_key}' not found in configuration. "
            f"Available: {list(products.keys())}"
        )
    return products[product_key]


def get_all_products() -> dict[str, Any]:
    """Get all product configurations."""
    config = load_contracts_config()
    return config.get("products", {})


def get_allowed_contracts(product_key: str) -> list[str]:
    """Get allowed contracts for a product."""
    product = get_product_config(product_key)
    return product.get("contracts", [])


def get_allowed_spreads(product_key: str) -> list[str]:
    """Get allowed spreads for a product."""
    product = get_product_config(product_key)
    return product.get("spreads", [])
