"""
Dependency injection container for the ZQ Strategy Planner.

Provides singleton service instances via FastAPI dependency injection.
Re-exports settings-level singletons and builds service-layer singletons.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from app.config.settings import (
    Settings,
    ContractLoader,
    ContractRegistry,
    StrategySettings,
    get_settings as _settings_singleton,
    get_contract_registry as _registry_singleton,
    get_strategy_settings as _strategy_settings_singleton,
)
from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.adapters.qh_adapter import QHAdapter
    from app.services.data_provider import DataProvider
    from app.services.indicator_engine import IndicatorEngine
    from app.services.regime_engine import RegimeEngine
    from app.services.risk_engine import RiskEngine
    from app.services.strategy_engine import StrategyEngine

logger = get_logger(__name__)


# Re-export the settings-level singletons so route code can import from one place
def get_settings() -> Settings:
    """Return cached application settings."""
    return _settings_singleton()


def get_contract_registry() -> ContractRegistry:
    """Return cached contract registry loaded from YAML."""
    return _registry_singleton()


def get_strategy_settings() -> StrategySettings:
    """Return cached strategy settings loaded from YAML."""
    return _strategy_settings_singleton()


@functools.lru_cache(maxsize=1)
def get_qh_adapter() -> "QHAdapter":
    """Return cached QH adapter instance."""
    from app.adapters.qh_adapter import QHAdapter

    settings = get_settings()
    adapter = QHAdapter(
        base_url=settings.market_data_api_url,
        api_key=settings.market_data_api_key,
    )
    logger.info("qh_adapter_initialized", base_url=settings.market_data_api_url)
    return adapter


@functools.lru_cache(maxsize=1)
def get_indicator_engine() -> "IndicatorEngine":
    """Return cached indicator engine instance."""
    from app.services.indicator_engine import IndicatorEngine

    ss = get_strategy_settings()
    config = {
        "atr": {"length": ss.indicators.atr.length, "smoothing": ss.indicators.atr.smoothing},
        "sma": {"lengths": list(ss.indicators.sma.lengths)},
        "ema": {"lengths": list(ss.indicators.ema.lengths)},
        "donchian": {"length": ss.indicators.donchian.length},
        "bollinger": {"length": ss.indicators.bollinger.length, "std_dev": ss.indicators.bollinger.std_dev},
        "dcw": {"length": ss.indicators.dcw.length},
    }
    engine = IndicatorEngine(config=config)
    logger.info("indicator_engine_initialized")
    return engine


@functools.lru_cache(maxsize=1)
def get_risk_engine() -> "RiskEngine":
    """Return cached risk engine instance."""
    from app.services.risk_engine import RiskEngine

    ss = get_strategy_settings()
    config = {
        "default_risk_per_trade_usd": ss.risk.default_risk_per_trade_usd,
        "max_risk_per_trade_usd": ss.risk.max_risk_per_trade_usd,
        "default_slippage_ticks": ss.risk.default_slippage_ticks,
        "default_commission_per_side": ss.risk.default_commission_per_side,
        "event_risk_reduction": ss.risk.event_risk_reduction,
        "max_position_size": ss.risk.max_position_size,
    }
    engine = RiskEngine(config=config)
    logger.info("risk_engine_initialized")
    return engine


@functools.lru_cache(maxsize=1)
def get_regime_engine() -> "RegimeEngine":
    """Return cached regime engine instance."""
    from app.services.regime_engine import RegimeEngine

    ss = get_strategy_settings()
    config = {
        "trend_atr_threshold": ss.regime.trend_atr_threshold,
        "volatility_atr_threshold": ss.regime.volatility_atr_threshold,
        "range_dcw_threshold": ss.regime.range_dcw_threshold,
        "event_window_hours": ss.regime.event_window_hours,
        "regime_expiry_hours": ss.regime.regime_expiry_hours,
    }
    engine = RegimeEngine(config=config)
    logger.info("regime_engine_initialized")
    return engine


@functools.lru_cache(maxsize=1)
def get_data_provider() -> "DataProvider":
    """Return cached data provider instance."""
    from app.services.data_provider import DataProvider

    settings = get_settings()
    adapter = get_qh_adapter()
    registry = get_contract_registry()
    provider = DataProvider(
        adapter=adapter,
        settings=settings,
        contract_registry=registry,
    )
    logger.info("data_provider_initialized")
    return provider


@functools.lru_cache(maxsize=1)
def get_strategy_engine() -> "StrategyEngine":
    """Return cached strategy engine instance."""
    from app.services.strategy_engine import StrategyEngine

    indicator_engine = get_indicator_engine()
    risk_engine = get_risk_engine()
    regime_engine = get_regime_engine()
    data_provider = get_data_provider()
    registry = get_contract_registry()
    ss = get_strategy_settings()

    config = {
        "min_bars_required": ss.strategy.min_bars_required,
        "confidence_threshold": ss.strategy.confidence_threshold,
        "max_simultaneous_signals": ss.strategy.max_simultaneous_signals,
    }

    engine = StrategyEngine(
        indicator_engine=indicator_engine,
        risk_engine=risk_engine,
        regime_engine=regime_engine,
        data_provider=data_provider,
        contract_registry=registry,
        config=config,
    )
    logger.info("strategy_engine_initialized")
    return engine
