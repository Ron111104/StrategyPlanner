"""FastAPI application factory and startup."""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.exceptions import StrategyPlannerError
from app.core.logging import setup_logging, get_logger
from app.core.settings import get_settings
from app.routes import (
    health_router,
    market_data_router,
    strategy_router,
    regime_router,
    account_router,
    ladder_router,
    pages_router,
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown."""
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL, settings.LOG_FORMAT)
    logger.info(
        "application_starting",
        app=settings.APP_NAME,
        env=settings.APP_ENV,
        host=settings.APP_HOST,
        port=settings.APP_PORT,
    )
    yield
    logger.info("application_shutting_down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    application = FastAPI(
        title=settings.APP_NAME,
        description="Institutional-grade CME Fed Funds Futures Strategy Planning Platform",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static files
    application.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

    # Templates
    templates = Jinja2Templates(directory=str(settings.templates_dir))
    application.state.templates = templates

    # Exception handlers
    @application.exception_handler(StrategyPlannerError)
    async def strategy_planner_error_handler(
        request: Request, exc: StrategyPlannerError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"error": exc.message, "detail": str(exc.detail) if exc.detail else None},
        )

    @application.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_error", error=str(exc), path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(exc)},
        )

    # Register routers
    application.include_router(health_router)
    application.include_router(market_data_router)
    application.include_router(strategy_router)
    application.include_router(regime_router)
    application.include_router(account_router)
    application.include_router(ladder_router)
    application.include_router(pages_router)

    return application


app = create_app()
