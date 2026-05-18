"""
Dependency injection container using dependency-injector.

Provides clean DI for all services, adapters, and engines.
"""

from __future__ import annotations

from dependency_injector import containers, providers

from app.config.settings import get_app_settings, get_qh_settings, load_contracts_config, load_strategy_settings


class Container(containers.DeclarativeContainer):
    """Application DI container."""

    wiring_config = containers.WiringConfiguration(
        modules=[
            "app.routes.market_data",
            "app.routes.strategy",
            "app.routes.regime",
            "app.routes.account",
            "app.routes.health",
        ]
    )

    # ── Configuration providers ───────────────────────────────
    app_settings = providers.Singleton(get_app_settings)
    qh_settings = providers.Singleton(get_qh_settings)
    contracts_config = providers.Singleton(load_contracts_config)
    strategy_settings = providers.Singleton(load_strategy_settings)

    # ── Adapters ──────────────────────────────────────────────
    qh_adapter = providers.Singleton(
        "app.adapters.qh_adapter.QHAdapter",
        settings=qh_settings,
    )

    # ── Services ──────────────────────────────────────────────
    contract_registry = providers.Singleton(
        "app.services.contract_registry.ContractRegistry",
        config=contracts_config,
    )

    indicator_engine = providers.Singleton(
        "app.services.indicator_engine.IndicatorEngine",
        settings=strategy_settings,
    )

    regime_engine = providers.Singleton(
        "app.services.regime_engine.RegimeEngine",
        settings=strategy_settings,
    )

    risk_engine = providers.Singleton(
        "app.services.risk_engine.RiskEngine",
        settings=strategy_settings,
    )

    data_provider = providers.Singleton(
        "app.services.data_provider.DataProvider",
        qh_adapter=qh_adapter,
        contract_registry=contract_registry,
    )

    strategy_engine = providers.Singleton(
        "app.services.strategy_engine.StrategyEngine",
        indicator_engine=indicator_engine,
        regime_engine=regime_engine,
        risk_engine=risk_engine,
        settings=strategy_settings,
    )
