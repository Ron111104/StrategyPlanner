# backend/app/routes/regime.py
"""Macro regime state management routes."""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from app.contracts.macro_inputs import (
    MacroBias,
    MarketRegime,
    RegimeState,
    RegimeUpdateRequest,
)
from app.core.dependencies import get_regime_engine
from app.core.exceptions import InvalidContractError, StrategyPlannerError
from app.services.regime_engine import RegimeEngine

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/regime",
    tags=["Regime"],
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error during regime operations",
        },
    },
)


# ---------------------------------------------------------------------------
# Schemas local to this router
# ---------------------------------------------------------------------------


class RegimeUpdateResponse(BaseModel):
    """Acknowledgement after a regime update."""

    product: str = Field(..., description="Product whose regime was updated")
    regime: str = Field(..., description="New regime label")
    message: str = Field(default="Regime updated successfully")


class RegimeHistoryResponse(BaseModel):
    """Response containing regime transition history."""

    product: str = Field(..., description="Product symbol")
    count: int = Field(..., ge=0, description="Number of regime entries")
    history: list[RegimeState] = Field(
        default_factory=list,
        description="Chronological list of regime states",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.put(
    "/update/{product}",
    response_model=RegimeUpdateResponse,
    status_code=status.HTTP_200_OK,
    summary="Update regime state",
    description=(
        "Accept a regime update for a product and persist it via the regime engine. "
        "This triggers downstream recalculation of strategy biases."
    ),
)
async def update_regime(
    product: Annotated[str, Path(description="ZQ product symbol")],
    request: RegimeUpdateRequest,
    regime_engine: Annotated[RegimeEngine, Depends(get_regime_engine)],
) -> RegimeUpdateResponse:
    log = logger.bind(product=product)
    log.info("regime.update.start", regime=request.regime.value if hasattr(request.regime, "value") else str(request.regime))
    try:
        await regime_engine.update_regime(product, request)
        regime_label = request.regime.value if hasattr(request.regime, "value") else str(request.regime)
        log.info("regime.update.success", regime=regime_label)
        return RegimeUpdateResponse(
            product=product,
            regime=regime_label,
            message=f"Regime for '{product}' updated to '{regime_label}'",
        )
    except InvalidContractError as exc:
        log.warning("regime.update.invalid_contract", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except StrategyPlannerError as exc:
        log.error("regime.update.engine_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        log.error("regime.update.failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update regime state",
        ) from exc


@router.get(
    "/current/{product}",
    response_model=RegimeState,
    status_code=status.HTTP_200_OK,
    summary="Get current regime state",
    description="Return the current macro regime state for the given product.",
)
async def get_current_regime(
    product: Annotated[str, Path(description="ZQ product symbol")],
    regime_engine: Annotated[RegimeEngine, Depends(get_regime_engine)],
) -> RegimeState:
    log = logger.bind(product=product)
    log.info("regime.current.start")
    try:
        state: RegimeState | None = await regime_engine.get_current_regime(product)
        if state is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No regime state found for product '{product}'",
            )
        log.info("regime.current.success")
        return state
    except HTTPException:
        raise
    except Exception as exc:
        log.error("regime.current.failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve current regime state",
        ) from exc


@router.get(
    "/history/{product}",
    response_model=RegimeHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get regime history",
    description="Return the chronological regime transition history for a product.",
)
async def get_regime_history(
    product: Annotated[str, Path(description="ZQ product symbol")],
    limit: Annotated[int, Query(ge=1, le=500, description="Max history entries")] = 100,
    regime_engine: Annotated[RegimeEngine, Depends(get_regime_engine)],
) -> RegimeHistoryResponse:
    log = logger.bind(product=product, limit=limit)
    log.info("regime.history.start")
    try:
        history: list[RegimeState] = await regime_engine.get_regime_history(product, limit=limit)
        log.info("regime.history.success", count=len(history))
        return RegimeHistoryResponse(
            product=product,
            count=len(history),
            history=history,
        )
    except Exception as exc:
        log.error("regime.history.failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve regime history",
        ) from exc
