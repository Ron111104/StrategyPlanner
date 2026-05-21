# backend/app/routes/health.py
"""System health and diagnostics routes."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.config.settings import Settings
from app.core.dependencies import (
    get_data_provider,
    get_regime_engine,
    get_settings,
    get_strategy_engine,
)
from app.services.data_provider import DataProvider
from app.services.regime_engine import RegimeEngine
from app.services.strategy_engine import StrategyEngine

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["System"],
)

# Module-level startup timestamp — set by main.py on startup
_startup_time: float = time.time()


def set_startup_time(t: float) -> None:
    """Called by main.py during the lifespan startup phase."""
    global _startup_time  # noqa: PLW0603
    _startup_time = t


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CacheSizes(BaseModel):
    """Current sizes of in-memory caches."""

    market_data_products: int = Field(default=0, ge=0, description="Number of products in data cache")
    regime_states: int = Field(default=0, ge=0, description="Number of regime state entries")
    strategy_signals: int = Field(default=0, ge=0, description="Number of cached strategy signals")


class HealthResponse(BaseModel):
    """System health check response."""

    status: str = Field(..., description="Overall system status")
    version: str = Field(..., description="Application version")
    uptime_seconds: float = Field(..., ge=0, description="Seconds since startup")
    timestamp: datetime = Field(..., description="Current server time (UTC)")
    cache_sizes: CacheSizes = Field(default_factory=CacheSizes, description="In-memory cache stats")


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="System health check",
    description=(
        "Return current system status including version, uptime, and "
        "cache sizes for monitoring and readiness probes."
    ),
)
async def health_check(
    settings: Annotated[Settings, Depends(get_settings)],
    data_provider: Annotated[DataProvider, Depends(get_data_provider)],
    strategy_engine: Annotated[StrategyEngine, Depends(get_strategy_engine)],
    regime_engine: Annotated[RegimeEngine, Depends(get_regime_engine)],
) -> HealthResponse:
    logger.debug("health.check")

    # Safely probe cache sizes — services may not expose these attributes yet
    market_data_count = 0
    regime_count = 0
    signal_count = 0

    try:
        if hasattr(data_provider, "_bar_cache"):
            market_data_count = len(data_provider._bar_cache)  # noqa: SLF001
        elif hasattr(data_provider, "bar_cache"):
            market_data_count = len(data_provider.bar_cache)
    except Exception:
        pass

    try:
        if hasattr(regime_engine, "_regime_cache"):
            regime_count = len(regime_engine._regime_cache)  # noqa: SLF001
        elif hasattr(regime_engine, "regime_cache"):
            regime_count = len(regime_engine.regime_cache)
    except Exception:
        pass

    try:
        if hasattr(strategy_engine, "_signal_cache"):
            signal_count = len(strategy_engine._signal_cache)  # noqa: SLF001
        elif hasattr(strategy_engine, "signal_cache"):
            signal_count = len(strategy_engine.signal_cache)
    except Exception:
        pass

    uptime = time.time() - _startup_time

    return HealthResponse(
        status="healthy",
        version=settings.app_version if hasattr(settings, "app_version") else "1.0.0",
        uptime_seconds=round(uptime, 2),
        timestamp=datetime.now(tz=timezone.utc),
        cache_sizes=CacheSizes(
            market_data_products=market_data_count,
            regime_states=regime_count,
            strategy_signals=signal_count,
        ),
    )
