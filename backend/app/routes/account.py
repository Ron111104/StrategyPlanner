"""
Account Routes — account configuration for risk parameters.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.contracts.execution_inputs import AccountConfig
from app.services.risk_engine import RiskEngine

router = APIRouter(prefix="/account", tags=["Account"])


def create_account_router(risk_engine: RiskEngine) -> APIRouter:
    """Factory to create account router with injected dependencies."""

    @router.get(
        "/config",
        summary="Get account config",
        description="Get current account risk configuration.",
        response_model=AccountConfig,
    )
    async def get_account_config() -> AccountConfig:
        return risk_engine.account_config

    @router.put(
        "/config",
        summary="Update account config",
        description="Update account risk configuration settings.",
        response_model=AccountConfig,
    )
    async def update_account_config(config: AccountConfig) -> AccountConfig:
        risk_engine.update_account(config)
        return risk_engine.account_config

    return router
