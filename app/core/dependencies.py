"""FastAPI dependency injection providers."""
from typing import AsyncGenerator

import httpx

from app.core.settings import get_settings, Settings


async def get_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an async HTTP client."""
    settings = get_settings()
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(settings.QH_API_TIMEOUT),
        headers={"Accept": "application/json"},
    ) as client:
        yield client


def get_app_settings() -> Settings:
    """Provide application settings."""
    return get_settings()
