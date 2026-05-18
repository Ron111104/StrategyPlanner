"""
Strategy Routes — thin API handlers for strategy evaluation and signal retrieval.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.contracts.engine_output import StrategyEvaluateRequest, StrategyEvaluateResponse
from app.contracts.market_data import ContractType
from app.services.contract_registry import ContractRegistry
from app.services.data_provider import DataProvider
from app.services.strategy_engine import StrategyEngine

router = APIRouter(prefix="/strategy", tags=["Strategy"])


def create_strategy_router(
    strategy_engine: StrategyEngine,
    data_provider: DataProvider,
    contract_registry: ContractRegistry,
) -> APIRouter:
    """Factory to create strategy router with injected dependencies."""

    @router.post(
        "/evaluate",
        summary="Evaluate strategies",
        description="Evaluate all applicable strategies for a product and return ranked signals.",
        response_model=StrategyEvaluateResponse,
    )
    async def evaluate_strategies(request: StrategyEvaluateRequest) -> StrategyEvaluateResponse:
        if not contract_registry.is_registered(request.product):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown product: {request.product}",
            )

        contract_type = contract_registry.get_contract_type(request.product)
        if contract_type is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot determine contract type for: {request.product}",
            )

        # Get cached bars
        bars = data_provider.get_bars(request.product)
        spread_bars = None

        if contract_type == ContractType.SPREAD:
            spread_bars = data_provider.get_spread_bars(request.product)
            # For spread evaluation, also get outright bars for legs
            legs = contract_registry.get_spread_legs(request.product)
            if legs:
                bars = data_provider.get_bars(legs[0])

        if not bars and not spread_bars:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No cached data for {request.product}. Fetch or ingest data first.",
            )

        response = strategy_engine.evaluate_all(
            bars=bars,
            spread_bars=spread_bars,
            product=request.product,
            contract_type=contract_type,
            timeframe=request.timeframe,
            regime_override=request.regime_override,
            strategy_filter=request.strategies,
        )

        return response

    @router.get(
        "/signal",
        summary="Get best signal",
        description="Get the highest-confidence signal from the latest evaluation.",
    )
    async def get_best_signal(product: str) -> dict[str, Any]:
        if not contract_registry.is_registered(product):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown product: {product}",
            )

        contract_type = contract_registry.get_contract_type(product) or ContractType.OUTRIGHT
        bars = data_provider.get_bars(product)
        spread_bars = data_provider.get_spread_bars(product) if contract_type == ContractType.SPREAD else None

        if not bars and not spread_bars:
            return {"signal": None, "reason": "No cached data"}

        response = strategy_engine.evaluate_all(
            bars=bars,
            spread_bars=spread_bars,
            product=product,
            contract_type=contract_type,
        )

        best = strategy_engine.select_strategy(response)
        if best:
            return {"signal": best.model_dump(mode="json")}
        return {"signal": None, "reason": "No qualifying signals"}

    @router.get(
        "/definitions",
        summary="Get strategy definitions",
        description="Get all available strategy definitions and their parameters.",
    )
    async def get_strategy_definitions() -> dict[str, Any]:
        from app.strategies.definitions import STRATEGY_REGISTRY
        return {
            "strategies": [
                {
                    "name": d.name.value,
                    "regimes": [r.value for r in d.regime_applicability],
                    "contract_types": [c.value for c in d.contract_types],
                    "priority": d.priority,
                    "risk_multiplier": d.risk_multiplier,
                    "volatility_suitability": d.volatility_suitability,
                    "description": d.description,
                }
                for d in STRATEGY_REGISTRY.values()
            ]
        }

    return router
