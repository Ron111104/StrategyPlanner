"""
Market Data Routes — thin API handlers for data ingestion and fetching.

NO business logic. Routes only handle:
- Request validation
- Response formatting
- Service delegation
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.contracts.market_data import MarketDataFetchRequest, MarketDataIngest
from app.services.contract_registry import ContractRegistry
from app.services.data_provider import DataProvider

router = APIRouter(prefix="/market-data", tags=["Market Data"])


def create_market_data_router(
    data_provider: DataProvider,
    contract_registry: ContractRegistry,
) -> APIRouter:
    """Factory to create market data router with injected dependencies."""

    @router.post(
        "/ingest",
        summary="Ingest OHLCV bars",
        description="Manually ingest OHLCV market data bars into the cache.",
        response_model=dict[str, Any],
    )
    async def ingest_market_data(request: MarketDataIngest) -> dict[str, Any]:
        if not contract_registry.is_registered(request.product):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown product: {request.product}. Register in contracts.yaml first.",
            )

        result = await data_provider.ingest(request)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=result,
            )
        return result

    @router.post(
        "/fetch",
        summary="Fetch OHLCV from external API",
        description="Fetch OHLCV data from the configured external market data API.",
        response_model=dict[str, Any],
    )
    async def fetch_market_data(request: MarketDataFetchRequest) -> dict[str, Any]:
        # Validate all products are registered
        for product in request.products:
            if not contract_registry.is_registered(product):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown product: {product}",
                )

        try:
            data = await data_provider.fetch(request)
            return {
                "status": "ok",
                "products_fetched": list(data.keys()),
                "bar_counts": {k: len(v) for k, v in data.items()},
                "cache_summary": data_provider.get_cache_summary(),
            }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"External API error: {str(e)}",
            )

    @router.get(
        "/cache",
        summary="Get cache summary",
        description="Get summary of all cached market data.",
    )
    async def get_cache_summary() -> dict[str, Any]:
        return data_provider.get_cache_summary()

    @router.get(
        "/contracts",
        summary="Get configured contracts",
        description="Get all configured outrights and spreads from the registry.",
    )
    async def get_contracts() -> dict[str, Any]:
        return contract_registry.to_dict()

    @router.get(
        "/snapshots",
        summary="Get market snapshots",
        description="Get all cached market snapshots for spread contracts.",
    )
    async def get_snapshots() -> dict[str, Any]:
        snapshots = data_provider.get_all_snapshots()
        return {
            k: v.model_dump(mode="json") for k, v in snapshots.items()
        }

    return router
