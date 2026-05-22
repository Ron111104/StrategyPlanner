"""Market data fetch and ingest routes."""
from fastapi import APIRouter, Depends, HTTPException
import httpx

from app.contracts.requests import FetchMarketDataRequest, IngestMarketDataRequest
from app.contracts.responses import MarketDataResponse, ErrorResponse
from app.core.dependencies import get_http_client
from app.core.exceptions import ContractNotFoundError, MarketDataError
from app.core.logging import get_logger
from app.services.cache import CacheManager
from app.services.data_provider import DataProvider
from app.services.indicator_engine import IndicatorEngine

logger = get_logger(__name__)
router = APIRouter(prefix="/market-data", tags=["market-data"])


@router.post("/fetch", response_model=MarketDataResponse)
async def fetch_market_data(
    request: FetchMarketDataRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> MarketDataResponse:
    """Fetch OHLCV data from the external API and cache it."""
    try:
        provider = DataProvider(client=client)
        return await provider.fetch_market_data(
            product_key=request.product_key,
            symbols=request.symbols,
            timeframe=request.timeframe,
        )
    except ContractNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except MarketDataError as e:
        raise HTTPException(status_code=502, detail=e.message)
    except Exception as e:
        logger.error("fetch_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest", response_model=MarketDataResponse)
async def ingest_market_data(
    request: IngestMarketDataRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> MarketDataResponse:
    """Fetch OHLCV data and compute indicators."""
    try:
        provider = DataProvider(client=client)
        result = await provider.fetch_market_data(
            product_key=request.product_key,
            symbols=request.symbols,
            timeframe=request.timeframe,
        )

        if request.compute_indicators:
            cache = CacheManager()
            engine = IndicatorEngine()
            for sym in request.symbols:
                series = cache.get_ohlcv(sym, request.timeframe)
                if series and not series.is_empty:
                    try:
                        engine.compute_all(series)
                    except Exception as e:
                        logger.warning("indicator_error", symbol=sym, error=str(e))
                        result.errors.append(f"Indicator error for {sym}: {str(e)}")

        return result
    except ContractNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except MarketDataError as e:
        raise HTTPException(status_code=502, detail=e.message)
    except Exception as e:
        logger.error("ingest_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshots")
async def get_snapshots() -> dict:
    """Get all cached market snapshots."""
    cache = CacheManager()
    snapshots = cache.get_all_snapshots()
    return {
        "snapshots": {k: v.model_dump() for k, v in snapshots.items()},
        "spreads": {k: v.model_dump() for k, v in cache.get_all_spreads().items()},
    }


@router.get("/ohlcv/{symbol}/{timeframe}")
async def get_ohlcv(symbol: str, timeframe: str) -> dict:
    """Get cached OHLCV data for charting."""
    cache = CacheManager()
    series = cache.get_ohlcv(symbol, timeframe)
    if not series:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}:{timeframe}")
    return {
        "symbol": series.symbol,
        "timeframe": series.timeframe,
        "bars": [b.model_dump() for b in series.bars],
        "count": series.length,
    }


@router.get("/indicators/{symbol}/{timeframe}")
async def get_indicators(symbol: str, timeframe: str) -> dict:
    """Get cached indicators for a symbol."""
    cache = CacheManager()
    indicators = cache.get_indicators(symbol, timeframe)
    if not indicators:
        raise HTTPException(status_code=404, detail=f"No indicators for {symbol}:{timeframe}")
    return indicators.model_dump()
