# backend/app/routes/strategy.py
"""Strategy evaluation, signal retrieval, and comparison routes."""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field

from app.contracts.engine_output import (
    StrategyEvaluateRequest,
    StrategyEvaluateResponse,
    StrategySignal,
)
from app.core.dependencies import get_strategy_engine
from app.core.exceptions import (
    InsufficientDataError,
    InvalidContractError,
    StrategyPlannerError,
)
from app.services.strategy_engine import StrategyEngine

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/strategy",
    tags=["Strategy"],
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error during strategy operations",
        },
    },
)


# ---------------------------------------------------------------------------
# Schemas local to this router
# ---------------------------------------------------------------------------


class StrategyDefinition(BaseModel):
    """Public metadata describing an available strategy."""

    name: str = Field(..., description="Strategy name identifier")
    description: str = Field(..., description="Human-readable strategy description")
    version: str = Field(..., description="Strategy version string")
    supported_products: list[str] = Field(
        default_factory=list,
        description="Products this strategy can evaluate",
    )
    parameters: dict[str, str] = Field(
        default_factory=dict,
        description="Configurable strategy parameters and their defaults",
    )


class StrategyListResponse(BaseModel):
    """Response listing all available strategies."""

    count: int = Field(..., ge=0, description="Total available strategies")
    strategies: list[StrategyDefinition]


class StrategyCompareRequest(BaseModel):
    """Request body for multi-strategy comparison."""

    evaluations: list[StrategyEvaluateRequest] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of strategy evaluation requests to compare (1-10)",
    )


class StrategyCompareItem(BaseModel):
    """Single comparison result."""

    strategy_name: str
    result: StrategyEvaluateResponse


class StrategyCompareResponse(BaseModel):
    """Response for multi-strategy comparison."""

    count: int = Field(..., ge=0, description="Number of strategies compared")
    results: list[StrategyCompareItem]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/evaluate",
    response_model=StrategyEvaluateResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate a strategy",
    description=(
        "Run the strategy engine against the provided parameters and market context. "
        "Returns signals, confidence, and supporting analytics."
    ),
)
async def evaluate_strategy(
    request: StrategyEvaluateRequest,
    strategy_engine: Annotated[StrategyEngine, Depends(get_strategy_engine)],
) -> StrategyEvaluateResponse:
    log = logger.bind(product=request.product, strategy=request.strategy_name)
    log.info("strategy.evaluate.start")
    try:
        result: StrategyEvaluateResponse = await strategy_engine.evaluate(request)
        log.info("strategy.evaluate.success", signal=result.signal.value if result.signal else None)
        return result
    except InsufficientDataError as exc:
        log.warning("strategy.evaluate.insufficient_data", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except InvalidContractError as exc:
        log.warning("strategy.evaluate.invalid_contract", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except StrategyPlannerError as exc:
        log.error("strategy.evaluate.planner_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        log.error("strategy.evaluate.failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Strategy evaluation failed unexpectedly",
        ) from exc


@router.get(
    "/signal/{product}",
    response_model=StrategySignal,
    status_code=status.HTTP_200_OK,
    summary="Get latest signal for a product",
    description="Return the most recent strategy signal computed for the given product.",
)
async def get_latest_signal(
    product: Annotated[str, Path(description="ZQ product symbol, e.g. ZQM2025")],
    strategy_engine: Annotated[StrategyEngine, Depends(get_strategy_engine)],
) -> StrategySignal:
    log = logger.bind(product=product)
    log.info("strategy.signal.start")
    try:
        signal: StrategySignal | None = await strategy_engine.get_latest_signal(product)
        if signal is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No signal available for product '{product}'",
            )
        log.info("strategy.signal.success", signal_value=signal.value if hasattr(signal, "value") else str(signal))
        return signal
    except HTTPException:
        raise
    except Exception as exc:
        log.error("strategy.signal.failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve latest signal",
        ) from exc


@router.get(
    "/strategies",
    response_model=StrategyListResponse,
    status_code=status.HTTP_200_OK,
    summary="List available strategies",
    description="Return metadata for all registered strategy definitions.",
)
async def list_strategies(
    strategy_engine: Annotated[StrategyEngine, Depends(get_strategy_engine)],
) -> StrategyListResponse:
    log = logger
    log.info("strategy.list.start")
    try:
        raw_strategies = await strategy_engine.list_strategies()
        definitions: list[StrategyDefinition] = [
            StrategyDefinition(
                name=s.get("name", "unknown"),
                description=s.get("description", ""),
                version=s.get("version", "0.0.0"),
                supported_products=s.get("supported_products", []),
                parameters=s.get("parameters", {}),
            )
            for s in raw_strategies
        ]
        log.info("strategy.list.success", count=len(definitions))
        return StrategyListResponse(count=len(definitions), strategies=definitions)
    except Exception as exc:
        log.error("strategy.list.failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list strategies",
        ) from exc


@router.post(
    "/compare",
    response_model=StrategyCompareResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare multiple strategies",
    description=(
        "Evaluate multiple strategy configurations in parallel and return "
        "a side-by-side comparison of results."
    ),
)
async def compare_strategies(
    request: StrategyCompareRequest,
    strategy_engine: Annotated[StrategyEngine, Depends(get_strategy_engine)],
) -> StrategyCompareResponse:
    log = logger.bind(strategy_count=len(request.evaluations))
    log.info("strategy.compare.start")

    results: list[StrategyCompareItem] = []
    errors: list[str] = []

    for eval_req in request.evaluations:
        try:
            result = await strategy_engine.evaluate(eval_req)
            results.append(
                StrategyCompareItem(
                    strategy_name=eval_req.strategy_name,
                    result=result,
                )
            )
        except (InsufficientDataError, InvalidContractError, StrategyPlannerError) as exc:
            log.warning(
                "strategy.compare.single_failed",
                strategy=eval_req.strategy_name,
                error=str(exc),
            )
            errors.append(f"{eval_req.strategy_name}: {exc}")
        except Exception as exc:
            log.error(
                "strategy.compare.single_unexpected",
                strategy=eval_req.strategy_name,
                error=str(exc),
            )
            errors.append(f"{eval_req.strategy_name}: unexpected error")

    if not results:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"All strategy evaluations failed: {'; '.join(errors)}",
        )

    log.info("strategy.compare.success", evaluated=len(results), failed=len(errors))
    return StrategyCompareResponse(count=len(results), results=results)
