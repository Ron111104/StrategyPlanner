# backend/app/routes/account.py
"""Account configuration, position sizing, risk profiling, and ladder planning routes."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from app.contracts.execution_inputs import AccountConfig
from app.core.dependencies import get_risk_engine, get_settings
from app.core.exceptions import StrategyPlannerError
from app.config.settings import Settings
from app.services.risk_engine import RiskEngine

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/account",
    tags=["Account"],
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error during account operations",
        },
    },
)


# ---------------------------------------------------------------------------
# Schemas local to this router
# ---------------------------------------------------------------------------


class TradeDirection(str, Enum):
    """Trade direction enum."""

    LONG = "long"
    SHORT = "short"


class AccountConfigResponse(BaseModel):
    """Wraps the returned account configuration."""

    config: AccountConfig
    message: str = Field(default="Account configuration retrieved")


class PositionSizingRequest(BaseModel):
    """Request for position size calculation."""

    account_balance: float = Field(..., gt=0, description="Current account balance in USD")
    risk_per_trade_pct: float = Field(
        ..., gt=0, le=100, description="Risk per trade as percentage of account"
    )
    entry_price: float = Field(..., gt=0, description="Planned entry price")
    stop_price: float = Field(..., gt=0, description="Planned stop-loss price")
    tick_value: float = Field(default=41.67, gt=0, description="Dollar value per tick (ZQ = $41.67)")
    tick_size: float = Field(default=0.005, gt=0, description="Minimum tick size")

    @model_validator(mode="after")
    def validate_prices(self) -> "PositionSizingRequest":
        if self.entry_price == self.stop_price:
            raise ValueError("Entry and stop prices must differ")
        return self


class PositionSizingResponse(BaseModel):
    """Computed position sizing result."""

    max_contracts: int = Field(..., ge=0, description="Maximum contracts based on risk")
    risk_per_contract: float = Field(..., description="Dollar risk per contract")
    total_risk: float = Field(..., description="Total dollar risk for position")
    risk_pct: float = Field(..., description="Actual risk as % of account")
    ticks_at_risk: float = Field(..., description="Number of ticks between entry and stop")


class RiskProfileRequest(BaseModel):
    """Request for computing a full risk profile."""

    entry_price: float = Field(..., gt=0, description="Entry price")
    stop_price: float = Field(..., gt=0, description="Stop-loss price")
    target_price: float = Field(..., gt=0, description="Target/take-profit price")
    size: int = Field(..., ge=1, description="Number of contracts")
    direction: TradeDirection = Field(..., description="Trade direction")
    tick_value: float = Field(default=41.67, gt=0, description="Dollar value per tick")
    tick_size: float = Field(default=0.005, gt=0, description="Minimum tick size")


class RiskProfile(BaseModel):
    """Computed risk profile for a trade."""

    direction: TradeDirection
    entry_price: float
    stop_price: float
    target_price: float
    size: int
    risk_ticks: float = Field(..., description="Ticks at risk")
    reward_ticks: float = Field(..., description="Ticks to target")
    risk_reward_ratio: float = Field(..., description="Reward-to-risk ratio")
    max_loss: float = Field(..., description="Maximum dollar loss")
    max_profit: float = Field(..., description="Maximum dollar profit")


class LadderRequest(BaseModel):
    """Request for generating a scaling ladder plan."""

    entry_price: float = Field(..., gt=0, description="Base entry price")
    stop_price: float = Field(..., gt=0, description="Stop-loss price")
    target_price: float = Field(..., gt=0, description="Final target price")
    size: int = Field(..., ge=1, description="Total contracts to distribute")
    levels: int = Field(..., ge=2, le=10, description="Number of ladder rungs (2-10)")
    direction: TradeDirection = Field(..., description="Trade direction")
    tick_value: float = Field(default=41.67, gt=0, description="Dollar value per tick")
    tick_size: float = Field(default=0.005, gt=0, description="Minimum tick size")


class LadderRung(BaseModel):
    """A single rung in the ladder plan."""

    level: int = Field(..., ge=1, description="Rung level number")
    price: float = Field(..., description="Entry price at this rung")
    contracts: int = Field(..., ge=0, description="Contracts at this rung")
    cumulative_contracts: int = Field(..., ge=0, description="Total contracts through this rung")


class LadderPlan(BaseModel):
    """Complete ladder scaling plan."""

    direction: TradeDirection
    total_contracts: int
    levels: int
    rungs: list[LadderRung]
    average_entry: float = Field(..., description="Weighted average entry price")
    total_risk: float = Field(..., description="Total dollar risk at full size")
    stop_price: float
    target_price: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.put(
    "/config",
    response_model=AccountConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Update account configuration",
    description="Store account configuration in the risk engine's internal cache.",
)
async def update_account_config(
    config: AccountConfig,
    risk_engine: Annotated[RiskEngine, Depends(get_risk_engine)],
) -> AccountConfigResponse:
    log = logger.bind(account_id=getattr(config, "account_id", "default"))
    log.info("account.config.update.start")
    try:
        risk_engine._account_cache = config  # noqa: SLF001 — intentional internal access
        log.info("account.config.update.success")
        return AccountConfigResponse(
            config=config,
            message="Account configuration updated successfully",
        )
    except Exception as exc:
        log.error("account.config.update.failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update account configuration",
        ) from exc


@router.get(
    "/config",
    response_model=AccountConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Get account configuration",
    description="Return the current account configuration from the risk engine cache.",
)
async def get_account_config(
    risk_engine: Annotated[RiskEngine, Depends(get_risk_engine)],
) -> AccountConfigResponse:
    log = logger
    log.info("account.config.get.start")
    try:
        config: AccountConfig | None = getattr(risk_engine, "_account_cache", None)
        if config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No account configuration has been set",
            )
        log.info("account.config.get.success")
        return AccountConfigResponse(config=config)
    except HTTPException:
        raise
    except Exception as exc:
        log.error("account.config.get.failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve account configuration",
        ) from exc


@router.post(
    "/sizing",
    response_model=PositionSizingResponse,
    status_code=status.HTTP_200_OK,
    summary="Compute position size",
    description=(
        "Calculate the optimal position size (number of contracts) based on "
        "account balance, risk tolerance, and entry/stop prices."
    ),
)
async def compute_position_sizing(
    request: PositionSizingRequest,
    risk_engine: Annotated[RiskEngine, Depends(get_risk_engine)],
) -> PositionSizingResponse:
    log = logger.bind(
        entry=request.entry_price,
        stop=request.stop_price,
        risk_pct=request.risk_per_trade_pct,
    )
    log.info("account.sizing.start")
    try:
        # Core sizing math
        price_diff = abs(request.entry_price - request.stop_price)
        ticks_at_risk = price_diff / request.tick_size
        risk_per_contract = ticks_at_risk * request.tick_value
        max_dollar_risk = request.account_balance * (request.risk_per_trade_pct / 100.0)

        if risk_per_contract <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Risk per contract is zero — entry and stop too close",
            )

        max_contracts = int(max_dollar_risk / risk_per_contract)
        total_risk = max_contracts * risk_per_contract
        actual_risk_pct = (total_risk / request.account_balance) * 100.0 if request.account_balance > 0 else 0.0

        log.info("account.sizing.success", contracts=max_contracts)
        return PositionSizingResponse(
            max_contracts=max_contracts,
            risk_per_contract=round(risk_per_contract, 2),
            total_risk=round(total_risk, 2),
            risk_pct=round(actual_risk_pct, 4),
            ticks_at_risk=round(ticks_at_risk, 2),
        )
    except HTTPException:
        raise
    except Exception as exc:
        log.error("account.sizing.failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute position sizing",
        ) from exc


@router.post(
    "/risk-profile",
    response_model=RiskProfile,
    status_code=status.HTTP_200_OK,
    summary="Compute risk profile",
    description=(
        "Compute a full risk profile for a planned trade, including risk/reward "
        "ratio, max loss, and max profit."
    ),
)
async def compute_risk_profile(
    request: RiskProfileRequest,
    risk_engine: Annotated[RiskEngine, Depends(get_risk_engine)],
) -> RiskProfile:
    log = logger.bind(
        direction=request.direction.value,
        entry=request.entry_price,
        stop=request.stop_price,
        target=request.target_price,
        size=request.size,
    )
    log.info("account.risk_profile.start")
    try:
        if request.direction == TradeDirection.LONG:
            risk_ticks = (request.entry_price - request.stop_price) / request.tick_size
            reward_ticks = (request.target_price - request.entry_price) / request.tick_size
        else:
            risk_ticks = (request.stop_price - request.entry_price) / request.tick_size
            reward_ticks = (request.entry_price - request.target_price) / request.tick_size

        if risk_ticks <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid stop placement — risk ticks must be positive for the given direction",
            )
        if reward_ticks <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid target placement — reward ticks must be positive for the given direction",
            )

        risk_reward_ratio = round(reward_ticks / risk_ticks, 4)
        max_loss = round(risk_ticks * request.tick_value * request.size, 2)
        max_profit = round(reward_ticks * request.tick_value * request.size, 2)

        log.info("account.risk_profile.success", rr_ratio=risk_reward_ratio)
        return RiskProfile(
            direction=request.direction,
            entry_price=request.entry_price,
            stop_price=request.stop_price,
            target_price=request.target_price,
            size=request.size,
            risk_ticks=round(risk_ticks, 2),
            reward_ticks=round(reward_ticks, 2),
            risk_reward_ratio=risk_reward_ratio,
            max_loss=max_loss,
            max_profit=max_profit,
        )
    except HTTPException:
        raise
    except Exception as exc:
        log.error("account.risk_profile.failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute risk profile",
        ) from exc


@router.post(
    "/ladder",
    response_model=LadderPlan,
    status_code=status.HTTP_200_OK,
    summary="Generate ladder scaling plan",
    description=(
        "Generate a multi-level entry ladder distributing contracts across "
        "price levels between the entry and a scaling boundary."
    ),
)
async def generate_ladder(
    request: LadderRequest,
    risk_engine: Annotated[RiskEngine, Depends(get_risk_engine)],
) -> LadderPlan:
    log = logger.bind(
        direction=request.direction.value,
        entry=request.entry_price,
        levels=request.levels,
        size=request.size,
    )
    log.info("account.ladder.start")
    try:
        # Determine scaling direction
        if request.direction == TradeDirection.LONG:
            # Scale in below entry (buying dips)
            step = (request.entry_price - request.stop_price) / (request.levels + 1)
            prices = [round(request.entry_price - step * i, 6) for i in range(request.levels)]
        else:
            # Scale in above entry (selling rallies)
            step = (request.stop_price - request.entry_price) / (request.levels + 1)
            prices = [round(request.entry_price + step * i, 6) for i in range(request.levels)]

        # Distribute contracts: front-load the first rungs
        base_per_level = request.size // request.levels
        remainder = request.size % request.levels
        contracts_per_rung: list[int] = []
        for i in range(request.levels):
            c = base_per_level + (1 if i < remainder else 0)
            contracts_per_rung.append(c)

        rungs: list[LadderRung] = []
        cumulative = 0
        weighted_sum = 0.0
        for idx, (price, qty) in enumerate(zip(prices, contracts_per_rung, strict=False)):
            cumulative += qty
            weighted_sum += price * qty
            rungs.append(
                LadderRung(
                    level=idx + 1,
                    price=price,
                    contracts=qty,
                    cumulative_contracts=cumulative,
                )
            )

        avg_entry = round(weighted_sum / request.size, 6) if request.size > 0 else 0.0

        # Total risk at full size
        if request.direction == TradeDirection.LONG:
            risk_ticks = (avg_entry - request.stop_price) / request.tick_size
        else:
            risk_ticks = (request.stop_price - avg_entry) / request.tick_size

        total_risk = round(abs(risk_ticks) * request.tick_value * request.size, 2)

        log.info("account.ladder.success", avg_entry=avg_entry, total_risk=total_risk)
        return LadderPlan(
            direction=request.direction,
            total_contracts=request.size,
            levels=request.levels,
            rungs=rungs,
            average_entry=avg_entry,
            total_risk=total_risk,
            stop_price=request.stop_price,
            target_price=request.target_price,
        )
    except HTTPException:
        raise
    except Exception as exc:
        log.error("account.ladder.failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate ladder plan",
        ) from exc
