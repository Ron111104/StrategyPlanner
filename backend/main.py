"""
CME Fed Funds Futures (ZQ) Strategy Planning Platform

Main FastAPI application entry point.
Assembles all layers: routes, services, adapters, and configuration.

This is a STRATEGY ENGINE and PLANNER ONLY.
It does NOT submit orders, route executions, or manage positions.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.qh_adapter import QHAdapter
from app.config.settings import (
    get_app_settings,
    get_qh_settings,
    load_contracts_config,
    load_strategy_settings,
)
from app.core.logging import configure_logging, get_logger
from app.routes.account import create_account_router
from app.routes.health import create_health_router
from app.routes.market_data import create_market_data_router
from app.routes.regime import create_regime_router
from app.routes.strategy import create_strategy_router
from app.services.contract_registry import ContractRegistry
from app.services.data_provider import DataProvider
from app.services.indicator_engine import IndicatorEngine
from app.services.regime_engine import RegimeEngine
from app.services.risk_engine import RiskEngine
from app.services.strategy_engine import StrategyEngine


# ── Module-level singletons (populated at startup) ───────────
_qh_adapter: QHAdapter | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle management."""
    global _qh_adapter

    logger = get_logger("startup")
    logger.info("starting_zq_strategy_planner")

    # Load configs
    app_settings = get_app_settings()
    qh_settings = get_qh_settings()
    contracts_config = load_contracts_config()
    strategy_settings = load_strategy_settings()

    configure_logging(app_settings.log_level)

    # Initialize services
    contract_registry = ContractRegistry(contracts_config)
    _qh_adapter = QHAdapter(qh_settings)
    data_provider = DataProvider(_qh_adapter, contract_registry)
    indicator_engine = IndicatorEngine(strategy_settings)
    regime_engine = RegimeEngine(strategy_settings)
    risk_engine = RiskEngine(strategy_settings)
    strategy_engine = StrategyEngine(
        indicator_engine=indicator_engine,
        regime_engine=regime_engine,
        risk_engine=risk_engine,
        settings=strategy_settings,
    )

    # Register routes with injected dependencies
    app.include_router(create_health_router())
    app.include_router(
        create_market_data_router(data_provider, contract_registry),
        prefix="/api",
    )
    app.include_router(
        create_strategy_router(strategy_engine, data_provider, contract_registry),
        prefix="/api",
    )
    app.include_router(create_regime_router(regime_engine), prefix="/api")
    app.include_router(create_account_router(risk_engine), prefix="/api")

    logger.info(
        "platform_ready",
        contracts=len(contract_registry.all_symbols()),
        strategies=7,
    )

    yield

    # Cleanup
    if _qh_adapter:
        await _qh_adapter.close()
    logger.info("platform_shutdown")


def create_app() -> FastAPI:
    """Factory to create the FastAPI application."""
    app_settings = get_app_settings()

    app = FastAPI(
        title="ZQ Strategy Planning Platform",
        description=(
            "Institutional-grade CME Fed Funds Futures (ZQ) strategy planning engine. "
            "Supports outright and calendar spread analysis, regime classification, "
            "multi-strategy evaluation, risk computation, and scenario planning. "
            "This is a PLANNING platform ONLY — no order submission or execution."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


app = create_app()
