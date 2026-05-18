"""
Health Routes — system health and readiness checks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


def create_health_router() -> APIRouter:
    """Factory to create health router."""

    @router.get(
        "/health",
        summary="Health check",
        description="System health and readiness check.",
    )
    async def health_check() -> dict[str, Any]:
        return {
            "status": "healthy",
            "service": "ZQ Strategy Planner",
            "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return router
