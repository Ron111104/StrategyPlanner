# backend/app/main.py
"""
ZQ Strategy Planner — Main FastAPI Application.

CME Fed Funds Futures (ZQ) Strategy Planning Platform.

Run with:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.exceptions import (
    DataFetchError,
    InsufficientDataError,
    InvalidContractError,
    StrategyPlannerError,
)
from app.core.logging import setup_logging
from app.config.settings import Settings
from app.core.dependencies import (
    get_contract_registry,
    get_data_provider,
    get_indicator_engine,
    get_regime_engine,
    get_risk_engine,
    get_settings,
    get_strategy_engine,
)

# Route imports
from app.routes.health import router as health_router, set_startup_time
from app.routes.market_data import router as market_data_router
from app.routes.strategy import router as strategy_router
from app.routes.regime import router as regime_router
from app.routes.account import router as account_router
from app.routes.pages import router as pages_router

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_APP_DIR = Path(__file__).resolve().parent
_STATIC_DIR = _APP_DIR / "static"


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown hooks."""
    # ── Startup ──────────────────────────────────────────────────────────
    start_ts = time.time()
    set_startup_time(start_ts)

    setup_logging()
    log = structlog.get_logger("app.startup")
    log.info("startup.begin", version="1.0.0")

    try:
        # Load settings
        settings = get_settings()
        log.info("startup.settings_loaded")

        # Load contract registry
        try:
            registry = get_contract_registry()
            log.info(
                "startup.contracts_loaded",
                count=len(registry.contracts) if hasattr(registry, "contracts") else "n/a",
            )
        except Exception as exc:
            log.warning("startup.contracts_load_skipped", reason=str(exc))

        # Initialize service singletons (triggers DI caching)
        try:
            get_data_provider()
            get_indicator_engine()
            get_strategy_engine()
            get_risk_engine()
            get_regime_engine()
            log.info("startup.services_initialized")
        except Exception as exc:
            log.warning("startup.services_partial_init", reason=str(exc))

        elapsed = round(time.time() - start_ts, 3)
        log.info("startup.complete", elapsed_seconds=elapsed)

    except Exception as exc:
        log.error("startup.failed", error=str(exc))
        raise

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    log = structlog.get_logger("app.shutdown")
    log.info("shutdown.begin")
    try:
        # Attempt graceful cleanup on services
        for svc_getter in (get_data_provider, get_strategy_engine, get_risk_engine, get_regime_engine):
            try:
                svc = svc_getter()
                if hasattr(svc, "shutdown"):
                    await svc.shutdown()
                elif hasattr(svc, "close"):
                    await svc.close()
            except Exception:
                pass
        log.info("shutdown.complete")
    except Exception as exc:
        log.error("shutdown.failed", error=str(exc))


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ZQ Strategy Planner",
    version="1.0.0",
    description=(
        "CME Fed Funds Futures (ZQ) Strategy Planning Platform — "
        "market data ingestion, strategy evaluation, regime tracking, "
        "risk management, and trade planning."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

if _STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
else:
    # Create the directory so the mount doesn't fail on fresh installs
    _STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

# CORS — permissive for development; tighten in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_timing_middleware(request: Request, call_next):
    """Inject X-Process-Time header and log request duration."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Process-Time-Ms"] = str(elapsed_ms)

    # Only log API calls (skip static/docs)
    path = request.url.path
    if path.startswith("/api"):
        structlog.get_logger("http").info(
            "request.completed",
            method=request.method,
            path=path,
            status_code=response.status_code,
            duration_ms=elapsed_ms,
        )
    return response


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(StrategyPlannerError)
async def strategy_planner_error_handler(request: Request, exc: StrategyPlannerError) -> JSONResponse:
    """Handle base StrategyPlannerError and its subclasses."""
    logger.error("exception.strategy_planner", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc), "error_type": type(exc).__name__},
    )


@app.exception_handler(InsufficientDataError)
async def insufficient_data_handler(request: Request, exc: InsufficientDataError) -> JSONResponse:
    """Handle insufficient data errors (404-ish)."""
    logger.warning("exception.insufficient_data", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc), "error_type": "InsufficientDataError"},
    )


@app.exception_handler(InvalidContractError)
async def invalid_contract_handler(request: Request, exc: InvalidContractError) -> JSONResponse:
    """Handle invalid contract specification errors."""
    logger.warning("exception.invalid_contract", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc), "error_type": "InvalidContractError"},
    )


@app.exception_handler(DataFetchError)
async def data_fetch_error_handler(request: Request, exc: DataFetchError) -> JSONResponse:
    """Handle external data fetch failures."""
    logger.error("exception.data_fetch", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": str(exc), "error_type": "DataFetchError"},
    )


# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------

# API routers (order matters for OpenAPI docs grouping)
app.include_router(health_router)
app.include_router(market_data_router)
app.include_router(strategy_router)
app.include_router(regime_router)
app.include_router(account_router)

# HTML page router — last, so API routes take precedence
app.include_router(pages_router)
