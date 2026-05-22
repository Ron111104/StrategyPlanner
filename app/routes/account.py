"""Account configuration routes."""
from fastapi import APIRouter, HTTPException

from app.contracts.requests import UpdateAccountConfigRequest
from app.contracts.responses import AccountConfigResponse
from app.core.logging import get_logger
from app.services.cache import CacheManager

logger = get_logger(__name__)
router = APIRouter(prefix="/account", tags=["account"])


@router.put("/config", response_model=AccountConfigResponse)
async def update_account_config(
    request: UpdateAccountConfigRequest,
) -> AccountConfigResponse:
    """Update account-level risk and sizing configuration."""
    try:
        cache = CacheManager()
        updates = request.model_dump(exclude_none=True)
        config = cache.update_account(updates)
        return AccountConfigResponse(success=True, config=config)
    except Exception as e:
        logger.error("account_update_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_account_config() -> dict:
    """Get current account configuration."""
    cache = CacheManager()
    return cache.get_account()
