# backend/app/routes/market_data.py
"""Market data ingestion, fetching, and snapshot routes for ZQ products."""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.contracts.market_data import (
    MarketDataIngest,
    OHLCVBar,
    Timeframe,
)
from app.contracts.external_api import MarketDataFetchRequest, MarketDataFetchResponse
from app.core.dependencies import get_data_provider, get_settings
from app.core.exceptions import (
    DataFetchError,
    InsufficientDataError,
    InvalidContractError,
)
from app.config.settings import Settings
from app.services.data_provider import DataProvider

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/market-data",
    tags=["Market Data"],
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error during market data operations",
        },
    },
)


# ---------------------------------------------------------------------------
# Schemas local to this router
# ---------------------------------------------------------------------------

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class IngestResponse(BaseModel):
    """Response after ingesting OHLCV bars."""

    product: str = Field(..., description="Product symbol ingested")
    bars_ingested: int = Field(..., ge=0, description="Number of bars successfully ingested")
    message: str = Field(default="Bars ingested successfully")


class MarketSnapshot(BaseModel):
    """Latest market snapshot for a product."""

    product: str = Field(..., description="Product symbol")
    last_price: float = Field(..., description="Last traded price")
    implied_rate: float = Field(..., description="Implied Fed Funds rate")
    timestamp: datetime = Field(..., description="Snapshot timestamp")
    bid: Optional[float] = Field(None, description="Best bid price")
    ask: Optional[float] = Field(None, description="Best ask price")
    volume: int = Field(default=0, ge=0, description="Session volume")
    open_interest: Optional[int] = Field(None, ge=0, description="Open interest")


class SpreadSnapshot(BaseModel):
    """Spread between two contract months."""

    front_product: str = Field(..., description="Front-month product symbol")
    back_product: str = Field(..., description="Back-month product symbol")
    spread: float = Field(..., description="Price spread (front - back)")
    implied_rate_spread: float = Field(..., description="Implied rate differential")
    front_price: float = Field(..., description="Front-month last price")
    back_price: float = Field(..., description="Back-month last price")
    timestamp: datetime = Field(..., description="Computation timestamp")


class BarsResponse(BaseModel):
    """Response containing cached bars for a product/timeframe."""

    product: str
    timeframe: str
    count: int = Field(..., ge=0, description="Number of bars returned")
    bars: list[OHLCVBar]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest OHLCV bars",
    description=(
        "Accept a batch of OHLCV bars for a ZQ product and persist them "
        "into the data provider's internal cache for downstream consumption."
    ),
)
async def ingest_bars(
    payload: MarketDataIngest,
    data_provider: Annotated[DataProvider, Depends(get_data_provider)],
) -> IngestResponse:
    log = logger.bind(product=payload.product, bar_count=len(payload.bars))
    log.info("market_data.ingest.start")
    try:
        count: int = await data_provider.ingest_bars(payload)
        log.info("market_data.ingest.success", ingested=count)
        return IngestResponse(
            product=payload.product,
            bars_ingested=count,
            message=f"Successfully ingested {count} bars for {payload.product}",
        )
    except InvalidContractError as exc:
        log.warning("market_data.ingest.invalid_contract", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        log.error("market_data.ingest.failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest market data bars",
        ) from exc


@router.post(
    "/fetch",
    response_model=MarketDataFetchResponse,
    status_code=status.HTTP_200_OK,
    summary="Fetch market data from external source",
    description=(
        "Fetch OHLCV bars from an external market data provider. "
        "Supports date-range and timeframe filtering."
    ),
)
async def fetch_bars(
    request: MarketDataFetchRequest,
    data_provider: Annotated[DataProvider, Depends(get_data_provider)],
) -> MarketDataFetchResponse:
    log = logger.bind(product=request.product)
    log.info("market_data.fetch.start")
    try:
        response: MarketDataFetchResponse = await data_provider.fetch_bars(request)
        log.info("market_data.fetch.success", bar_count=len(response.bars))
        return response
    except DataFetchError as exc:
        log.error("market_data.fetch.data_fetch_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except InvalidContractError as exc:
        log.warning("market_data.fetch.invalid_contract", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        log.error("market_data.fetch.failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch market data",
        ) from exc


@router.get(
    "/snapshot/{product}",
    response_model=MarketSnapshot,
    status_code=status.HTTP_200_OK,
    summary="Get latest market snapshot",
    description=(
        "Return the latest MarketSnapshot for the given product symbol, "
        "including last price, implied rate, bid/ask, and volume."
    ),
)
async def get_snapshot(
    product: Annotated[str, Path(description="ZQ product symbol, e.g. ZQM2025")],
    data_provider: Annotated[DataProvider, Depends(get_data_provider)],
) -> MarketSnapshot:
    log = logger.bind(product=product)
    log.info("market_data.snapshot.start")
    try:
        snapshot = await data_provider.get_snapshot(product)
        if snapshot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No snapshot available for product '{product}'",
            )
        log.info("market_data.snapshot.success")
        return snapshot
    except HTTPException:
        raise
    except InsufficientDataError as exc:
        log.warning("market_data.snapshot.insufficient_data", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        log.error("market_data.snapshot.failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve market snapshot",
        ) from exc


@router.get(
    "/bars/{product}/{timeframe}",
    response_model=BarsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get cached bars",
    description="Return cached OHLCV bars for a product and timeframe.",
)
async def get_bars(
    product: Annotated[str, Path(description="ZQ product symbol")],
    timeframe: Annotated[str, Path(description="Timeframe string, e.g. '1d', '1h'")],
    limit: Annotated[int, Query(ge=1, le=5000, description="Max bars to return")] = 500,
    data_provider: Annotated[DataProvider, Depends(get_data_provider)],
) -> BarsResponse:
    log = logger.bind(product=product, timeframe=timeframe, limit=limit)
    log.info("market_data.bars.start")
    try:
        bars: list[OHLCVBar] = await data_provider.get_bars(product, timeframe, limit=limit)
        log.info("market_data.bars.success", count=len(bars))
        return BarsResponse(
            product=product,
            timeframe=timeframe,
            count=len(bars),
            bars=bars,
        )
    except InvalidContractError as exc:
        log.warning("market_data.bars.invalid_contract", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except InsufficientDataError as exc:
        log.warning("market_data.bars.insufficient_data", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        log.error("market_data.bars.failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cached bars",
        ) from exc


@router.get(
    "/spread/{front}/{back}",
    response_model=SpreadSnapshot,
    status_code=status.HTTP_200_OK,
    summary="Compute spread snapshot",
    description=(
        "Compute and return the price/implied-rate spread between two ZQ "
        "contract months (front and back)."
    ),
)
async def get_spread(
    front: Annotated[str, Path(description="Front-month product symbol")],
    back: Annotated[str, Path(description="Back-month product symbol")],
    data_provider: Annotated[DataProvider, Depends(get_data_provider)],
) -> SpreadSnapshot:
    log = logger.bind(front=front, back=back)
    log.info("market_data.spread.start")
    try:
        front_snap = await data_provider.get_snapshot(front)
        back_snap = await data_provider.get_snapshot(back)

        if front_snap is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No snapshot available for front-month product '{front}'",
            )
        if back_snap is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No snapshot available for back-month product '{back}'",
            )

        spread_val = front_snap.last_price - back_snap.last_price
        implied_rate_spread = front_snap.implied_rate - back_snap.implied_rate

        log.info(
            "market_data.spread.success",
            spread=spread_val,
            implied_rate_spread=implied_rate_spread,
        )
        return SpreadSnapshot(
            front_product=front,
            back_product=back,
            spread=round(spread_val, 6),
            implied_rate_spread=round(implied_rate_spread, 6),
            front_price=front_snap.last_price,
            back_price=back_snap.last_price,
            timestamp=front_snap.timestamp,
        )
    except HTTPException:
        raise
    except InsufficientDataError as exc:
        log.warning("market_data.spread.insufficient_data", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        log.error("market_data.spread.failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute spread snapshot",
        ) from exc
