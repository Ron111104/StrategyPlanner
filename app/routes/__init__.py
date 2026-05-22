from app.routes.health import router as health_router
from app.routes.market_data import router as market_data_router
from app.routes.strategy import router as strategy_router
from app.routes.regime import router as regime_router
from app.routes.account import router as account_router
from app.routes.ladder import router as ladder_router
from app.routes.pages import router as pages_router

__all__ = [
    "health_router",
    "market_data_router",
    "strategy_router",
    "regime_router",
    "account_router",
    "ladder_router",
    "pages_router",
]
