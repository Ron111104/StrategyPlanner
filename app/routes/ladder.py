"""Ladder generation API routes."""
from fastapi import APIRouter, HTTPException

from app.contracts.ladder import LadderRequest, LadderResponse
from app.core.exceptions import InsufficientDataError, ConfigurationError
from app.services.ladder_engine import LadderEngine
from app.services.mtf_engine import MTFEngine

router = APIRouter(prefix="/ladder", tags=["ladder"])

_ladder_engine = LadderEngine()
_mtf_engine = MTFEngine()


@router.post("/generate", response_model=LadderResponse)
async def generate_ladder(request: LadderRequest) -> LadderResponse:
    """Generate an adaptive strategy ladder."""
    try:
        ladder = _ladder_engine.generate(request)
        warnings: list[str] = []

        # MTF analysis
        try:
            mtf = _mtf_engine.analyze(request.symbol, request.timeframe)
            if mtf.warnings:
                warnings.extend(mtf.warnings)
        except Exception:
            pass

        return LadderResponse(success=True, ladder=ladder, warnings=warnings)

    except InsufficientDataError as e:
        return LadderResponse(success=False, errors=[str(e)])
    except ConfigurationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies")
async def list_strategies() -> dict:
    """List available strategies for ladder generation."""
    from app.strategies import STRATEGY_REGISTRY
    from app.config.loader import load_strategy_settings
    settings = load_strategy_settings().get("strategies", {})
    strategies = []
    for name in STRATEGY_REGISTRY:
        cfg = settings.get(name, {})
        strategies.append({
            "name": name,
            "enabled": cfg.get("enabled", True),
            "priority": cfg.get("priority", 99),
            "applicable_regimes": cfg.get("applicable_regimes", []),
            "applicable_timeframes": cfg.get("applicable_timeframes", []),
            "spread_only": cfg.get("spread_only", False),
        })
    strategies.sort(key=lambda s: s["priority"])
    return {"strategies": strategies}


@router.get("/mtf/{symbol}/{timeframe}")
async def mtf_analysis(symbol: str, timeframe: str) -> dict:
    """Run multi-timeframe analysis for a symbol."""
    try:
        mtf = _mtf_engine.analyze(symbol, timeframe)
        return {
            "success": True,
            "analysis": mtf.to_dict(),
            "adjustments": {
                "spacing": _mtf_engine.get_spacing_adjustment(mtf),
                "confidence": _mtf_engine.get_confidence_adjustment(mtf),
                "size": _mtf_engine.get_size_adjustment(mtf),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
