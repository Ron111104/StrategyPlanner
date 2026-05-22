"""Tests for configuration loading."""
import pytest

from app.config.loader import (
    load_contracts_config,
    load_strategy_settings,
    get_product_config,
    get_all_products,
    get_allowed_contracts,
    get_allowed_spreads,
)
from app.core.exceptions import ConfigurationError


class TestContractsConfig:
    def test_load_contracts(self):
        config = load_contracts_config()
        assert "products" in config
        assert "fed_funds" in config["products"]
        assert "sofr" in config["products"]

    def test_fed_funds_config(self):
        product = get_product_config("fed_funds")
        assert product["product_code"] == "ZQ"
        assert product["outright_tick_size"] == 0.005
        assert product["outright_tick_value"] == 20.835
        assert product["spread_tick_size_bp"] == 0.5
        assert len(product["contracts"]) > 0
        assert len(product["spreads"]) > 0

    def test_sofr_config(self):
        product = get_product_config("sofr")
        assert product["product_code"] == "SR3"
        assert product["outright_tick_size"] == 0.0025

    def test_invalid_product_raises(self):
        with pytest.raises(ConfigurationError):
            get_product_config("nonexistent")

    def test_get_all_products(self):
        products = get_all_products()
        assert len(products) >= 2

    def test_allowed_contracts(self):
        contracts = get_allowed_contracts("fed_funds")
        assert "FFN26" in contracts
        assert "FFQ26" in contracts

    def test_allowed_spreads(self):
        spreads = get_allowed_spreads("fed_funds")
        assert "FFN26-FFQ26" in spreads


class TestStrategySettings:
    def test_load_settings(self):
        settings = load_strategy_settings()
        assert "indicators" in settings
        assert "strategies" in settings
        assert "risk" in settings

    def test_indicator_defaults(self):
        settings = load_strategy_settings()
        atr = settings["indicators"]["atr"]
        assert atr["default_length"] == 14

    def test_strategy_definitions(self):
        settings = load_strategy_settings()
        strats = settings["strategies"]
        assert "trend_fed_repricing" in strats
        assert "mean_reversion_range" in strats
        assert strats["trend_fed_repricing"]["enabled"] is True

    def test_risk_settings(self):
        settings = load_strategy_settings()
        risk = settings["risk"]
        assert risk["max_position_lots"] == 100
        assert risk["max_risk_per_trade_usd"] == 50000.0

    def test_timeframe_settings(self):
        settings = load_strategy_settings()
        tf = settings["timeframes"]
        assert "1H" in tf["allowed"]
        assert tf["default_chart"] == "1H"
