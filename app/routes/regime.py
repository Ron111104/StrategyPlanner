"""Regime management routes."""
from fastapi import APIRouter, HTTPException

from app.contracts.requests import UpdateRegimeRequest
from app.contracts.responses import RegimeResponse
from app.core.logging import get_logger
from app.services.regime_engine import RegimeEngine
from app.services.cache import CacheManager

logger = get_logger(__name__)
router = APIRouter(prefix="/regime", tags=["regime"])


@router.put("/update", response_model=RegimeResponse)
async def update_regime(request: UpdateRegimeRequest) -> RegimeResponse:
    """Manually update market regime and macro bias."""
    try:
        engine = RegimeEngine()
        state = engine.set_regime(
            regime=request.regime,
            macro_bias=request.macro_bias,
            notes=request.notes,
        )
        return RegimeResponse(success=True, state=state)
    except Exception as e:
        logger.error("regime_update_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/current")
async def get_current_regime() -> dict:
    """Get current regime state."""
    cache = CacheManager()
    state = cache.get_regime()
    return state.model_dump()


@router.get("/suggest/{symbol}/{timeframe}")
async def suggest_regime(symbol: str, timeframe: str) -> dict:
    """Get regime suggestion based on indicators (advisory only)."""
    cache = CacheManager()
    indicators = cache.get_indicators(symbol, timeframe)
    if not indicators:
        raise HTTPException(
            status_code=404,
            detail=f"No indicators for {symbol}:{timeframe}. Ingest data first.",
        )
    engine = RegimeEngine()
    scores = engine.suggest_regime(indicators)
    return {"symbol": symbol, "timeframe": timeframe, "suggestions": scores}
