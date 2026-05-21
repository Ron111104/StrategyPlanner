# backend/app/routes/pages.py
"""HTML page-serving routes (Jinja2 template rendering)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config.settings import ContractRegistry, Settings
from app.core.dependencies import get_contract_registry, get_settings

logger = structlog.get_logger(__name__)

# Resolve template directory relative to this file
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

router = APIRouter(
    tags=["Pages"],
    default_response_class=HTMLResponse,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_context(
    request: Request,
    settings: Settings,
    contracts: ContractRegistry,
    *,
    page_title: str = "ZQ Strategy Planner",
) -> dict[str, Any]:
    """Build the common template context dict."""
    return {
        "request": request,
        "page_title": page_title,
        "app_name": "ZQ Strategy Planner",
        "version": getattr(settings, "app_version", "1.0.0"),
        "settings": settings,
        "contracts": contracts,
    }


def _render(
    template_name: str,
    request: Request,
    settings: Settings,
    contracts: ContractRegistry,
    *,
    page_title: str = "ZQ Strategy Planner",
    extra: dict[str, Any] | None = None,
) -> HTMLResponse:
    """Render a Jinja2 template with standard context + optional extras."""
    ctx = _base_context(request, settings, contracts, page_title=page_title)
    if extra:
        ctx.update(extra)

    try:
        return templates.TemplateResponse(name=template_name, context=ctx)
    except Exception as exc:
        logger.error("pages.render.failed", template=template_name, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to render page: {template_name}",
        ) from exc


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------


@router.get(
    "/",
    summary="Dashboard",
    description="Render the main dashboard / index page.",
)
async def index_page(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    contracts: Annotated[ContractRegistry, Depends(get_contract_registry)],
) -> HTMLResponse:
    logger.info("pages.render", page="dashboard")
    return _render(
        "dashboard/index.html",
        request,
        settings,
        contracts,
        page_title="Dashboard — ZQ Strategy Planner",
    )


@router.get(
    "/strategy",
    summary="Strategy Evaluator",
    description="Render the strategy evaluation page.",
)
async def strategy_page(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    contracts: Annotated[ContractRegistry, Depends(get_contract_registry)],
) -> HTMLResponse:
    logger.info("pages.render", page="strategy_evaluator")
    return _render(
        "strategy/evaluator.html",
        request,
        settings,
        contracts,
        page_title="Strategy Evaluator — ZQ Strategy Planner",
    )


@router.get(
    "/strategy/spread",
    summary="Spread Analysis",
    description="Render the spread analysis page.",
)
async def spread_analysis_page(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    contracts: Annotated[ContractRegistry, Depends(get_contract_registry)],
) -> HTMLResponse:
    logger.info("pages.render", page="spread_analysis")
    return _render(
        "strategy/spread_analysis.html",
        request,
        settings,
        contracts,
        page_title="Spread Analysis — ZQ Strategy Planner",
    )


@router.get(
    "/strategy/regime",
    summary="Regime View",
    description="Render the macro regime visualization page.",
)
async def regime_view_page(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    contracts: Annotated[ContractRegistry, Depends(get_contract_registry)],
) -> HTMLResponse:
    logger.info("pages.render", page="regime_view")
    return _render(
        "strategy/regime_view.html",
        request,
        settings,
        contracts,
        page_title="Regime View — ZQ Strategy Planner",
    )


@router.get(
    "/risk",
    summary="Ladder Planner",
    description="Render the risk / ladder planner page.",
)
async def ladder_page(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    contracts: Annotated[ContractRegistry, Depends(get_contract_registry)],
) -> HTMLResponse:
    logger.info("pages.render", page="ladder")
    return _render(
        "risk/ladder.html",
        request,
        settings,
        contracts,
        page_title="Ladder Planner — ZQ Strategy Planner",
    )


@router.get(
    "/risk/sizing",
    summary="Position Sizing",
    description="Render the position sizing calculator page.",
)
async def sizing_page(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    contracts: Annotated[ContractRegistry, Depends(get_contract_registry)],
) -> HTMLResponse:
    logger.info("pages.render", page="sizing")
    return _render(
        "risk/sizing.html",
        request,
        settings,
        contracts,
        page_title="Position Sizing — ZQ Strategy Planner",
    )


@router.get(
    "/risk/scenarios",
    summary="Scenarios",
    description="Render the risk scenarios analysis page.",
)
async def scenarios_page(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    contracts: Annotated[ContractRegistry, Depends(get_contract_registry)],
) -> HTMLResponse:
    logger.info("pages.render", page="scenarios")
    return _render(
        "risk/scenarios.html",
        request,
        settings,
        contracts,
        page_title="Risk Scenarios — ZQ Strategy Planner",
    )


@router.get(
    "/replay",
    summary="Replay Engine",
    description="Render the historical replay engine page.",
)
async def replay_page(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    contracts: Annotated[ContractRegistry, Depends(get_contract_registry)],
) -> HTMLResponse:
    logger.info("pages.render", page="replay")
    return _render(
        "replay/replay_engine.html",
        request,
        settings,
        contracts,
        page_title="Replay Engine — ZQ Strategy Planner",
    )
