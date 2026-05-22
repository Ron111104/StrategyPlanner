"""Strategy evaluation and signal routes."""
from fastapi import APIRouter, HTTPException

from app.contracts.requests import EvaluateStrategyRequest
from app.contracts.regime import RegimeState
from app.contracts.responses import SignalResponse, StrategyEvalResponse
from app.core.exceptions import StrategyError
from app.core.logging import get_logger
from app.services.strategy_engine import StrategyEngine
from app.services.cache import CacheManager
from app.services.risk_engine import RiskEngine

logger = get_logger(__name__)
router = APIRouter(prefix="/strategy", tags=["strategy"])


@router.post("/evaluate", response_model=StrategyEvalResponse)
async def evaluate_strategies(request: EvaluateStrategyRequest) -> StrategyEvalResponse:
    """Evaluate strategies for the given symbols."""
    try:
        engine = StrategyEngine()
        regime_override = None
        if request.regime and request.macro_bias:
            regime_override = RegimeState(
                regime=request.regime,
                macro_bias=request.macro_bias,
            )

        results = engine.evaluate(
            product_key=request.product_key,
            symbols=request.symbols,
            timeframe=request.timeframe,
            strategy_names=request.strategies,
            regime_override=regime_override,
        )

        total_signals = sum(len(r.signals) for r in results)

        return StrategyEvalResponse(
            success=True,
            results=results,
            total_signals=total_signals,
        )
    except Exception as e:
        logger.error("strategy_eval_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals", response_model=SignalResponse)
async def get_signals() -> SignalResponse:
    """Get all current cached signals."""
    engine = StrategyEngine()
    cache = CacheManager()
    cards = engine.get_all_signal_cards()
    regime = cache.get_regime()
    return SignalResponse(cards=cards, regime=regime)


@router.get("/risk/{symbol}")
async def get_risk_assessment(
    symbol: str,
    direction: str = "long",
    entry: float = 0,
    stop: float = 0,
    target: float = 0,
    product_key: str = "fed_funds",
    timeframe: str = "1H",
) -> dict:
    """Compute risk assessment for a planned trade."""
    if entry == 0 or stop == 0 or target == 0:
        raise HTTPException(status_code=400, detail="entry, stop, and target are required")

    try:
        risk_engine = RiskEngine()
        is_spread = "-" in symbol
        profile = risk_engine.compute_risk_profile(
            symbol=symbol,
            direction=direction,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            product_key=product_key,
            is_spread=is_spread,
        )
        assessment = risk_engine.assess_trade(profile, symbol, timeframe)
        return assessment.model_dump()
    except Exception as e:
        logger.error("risk_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
