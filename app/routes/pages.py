"""Page routes serving Jinja2 templates."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.config.loader import get_all_products, load_strategy_settings
from app.services.cache import CacheManager

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Main dashboard page."""
    products = get_all_products()
    cache = CacheManager()
    regime = cache.get_regime()
    snapshots = cache.get_all_snapshots()
    spreads = cache.get_all_spreads()
    signals = cache.get_all_signal_cards()

    return request.app.state.templates.TemplateResponse(
        "dashboard/index.html",
        {
            "request": request,
            "products": products,
            "regime": regime,
            "snapshots": snapshots,
            "spreads": spreads,
            "signals": signals,
            "page_title": "Dashboard",
        },
    )


@router.get("/strategy", response_class=HTMLResponse)
async def strategy_page(request: Request) -> HTMLResponse:
    """Strategy analysis page."""
    products = get_all_products()
    settings = load_strategy_settings()
    cache = CacheManager()
    regime = cache.get_regime()

    return request.app.state.templates.TemplateResponse(
        "strategy/index.html",
        {
            "request": request,
            "products": products,
            "strategy_settings": settings.get("strategies", {}),
            "regime": regime,
            "page_title": "Strategy Planner",
        },
    )


@router.get("/risk", response_class=HTMLResponse)
async def risk_page(request: Request) -> HTMLResponse:
    """Risk analysis page."""
    products = get_all_products()
    cache = CacheManager()
    account = cache.get_account()

    regime = cache.get_regime()
    return request.app.state.templates.TemplateResponse(
        "risk/index.html",
        {
            "request": request,
            "products": products,
            "account": account,
            "regime": regime,
            "page_title": "Risk Planner",
        },
    )


@router.get("/ladder", response_class=HTMLResponse)
async def ladder_page(request: Request) -> HTMLResponse:
    """Adaptive strategy ladder page."""
    products = get_all_products()
    cache = CacheManager()
    regime = cache.get_regime()

    return request.app.state.templates.TemplateResponse(
        "ladder/index.html",
        {
            "request": request,
            "products": products,
            "regime": regime,
            "page_title": "Ladder Planner",
        },
    )


@router.get("/replay", response_class=HTMLResponse)
async def replay_page(request: Request) -> HTMLResponse:
    """Historical replay page."""
    products = get_all_products()

    cache = CacheManager()
    regime = cache.get_regime()
    return request.app.state.templates.TemplateResponse(
        "replay/index.html",
        {
            "request": request,
            "products": products,
            "regime": regime,
            "page_title": "Replay Engine",
        },
    )
