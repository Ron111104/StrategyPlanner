"""
Regime Routes — regime state management and manual override.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.contracts.macro_inputs import RegimeState, RegimeUpdateRequest
from app.services.regime_engine import RegimeEngine

router = APIRouter(prefix="/regime", tags=["Regime"])


def create_regime_router(regime_engine: RegimeEngine) -> APIRouter:
    """Factory to create regime router with injected dependencies."""

    @router.get(
        "/current",
        summary="Get current regime",
        description="Get the current market regime classification.",
        response_model=RegimeState,
    )
    async def get_current_regime() -> RegimeState:
        return regime_engine.current_state

    @router.put(
        "/update",
        summary="Update regime",
        description="Manually override market regime, macro bias, or event state.",
        response_model=RegimeState,
    )
    async def update_regime(request: RegimeUpdateRequest) -> RegimeState:
        return regime_engine.update(request)

    @router.delete(
        "/events",
        summary="Clear events",
        description="Clear all scheduled macro events.",
    )
    async def clear_events() -> dict[str, str]:
        regime_engine.clear_events()
        return {"status": "events_cleared"}

    return router
