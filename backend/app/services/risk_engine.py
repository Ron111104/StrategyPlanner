"""
Risk management engine for CME Fed Funds Futures (ZQ) Strategy Planning Platform.

Handles position sizing, risk-reward profiling, scaling ladder generation,
and round-trip cost computation.
"""
from __future__ import annotations

import math
from typing import Any

import structlog

from app.contracts.execution_inputs import (
    AccountConfig,
    LadderPlan,
    PositionSizingRequest,
    RiskProfile,
    ScaleLevel,
)
from app.utils.math_helpers import (
    dollar_value_of_ticks,
    round_to_tick,
    safe_divide,
    ticks_between,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class RiskEngine:
    """Computes risk profiles, position sizes, and scaling ladders."""

    __slots__ = ("_account_cache",)

    def __init__(self) -> None:
        self._account_cache: dict[str, AccountConfig] = {}

    # ------------------------------------------------------------------
    # Account management
    # ------------------------------------------------------------------

    def set_account(self, account_id: str, config: AccountConfig) -> None:
        """Cache an account configuration."""
        self._account_cache[account_id] = config
        logger.info("account_cached", account_id=account_id)

    def get_account(self, account_id: str) -> AccountConfig | None:
        """Return cached account config, or ``None``."""
        return self._account_cache.get(account_id)

    # ------------------------------------------------------------------
    # Risk Profile
    # ------------------------------------------------------------------

    def compute_risk_profile(
        self,
        entry_price: float,
        stop_price: float,
        target_price: float,
        position_size: int,
        direction: str,
        tick_size: float,
        tick_value: float,
        slippage_ticks: int = 1,
        commission_per_side: float = 2.50,
    ) -> RiskProfile:
        """Build a full risk profile for a proposed trade.

        Parameters
        ----------
        entry_price, stop_price, target_price:
            Trade price levels.
        position_size:
            Number of contracts.
        direction:
            ``"long"`` or ``"short"``.
        tick_size:
            Minimum price increment (e.g. 0.0025 for ZQ).
        tick_value:
            Dollar value of one tick per contract (e.g. $10.4175).
        slippage_ticks:
            Assumed slippage per side in ticks.
        commission_per_side:
            Commission per contract per side.

        Returns
        -------
        RiskProfile
        """
        log = logger.bind(direction=direction, entry=entry_price)

        # Tick-based risk/target
        tick_risk = ticks_between(entry_price, stop_price, tick_size)
        tick_target = ticks_between(entry_price, target_price, tick_size)

        # Dollar values
        dollar_risk_per_contract = dollar_value_of_ticks(tick_risk, tick_value)
        dollar_target_per_contract = dollar_value_of_ticks(tick_target, tick_value)

        dollar_risk = dollar_risk_per_contract * position_size
        dollar_target = dollar_target_per_contract * position_size

        # Risk : reward
        risk_reward = safe_divide(dollar_target, dollar_risk)

        # Costs
        slippage_cost = slippage_ticks * tick_value * position_size * 2  # round trip
        commission_cost = commission_per_side * 2 * position_size
        total_cost = slippage_cost + commission_cost

        # Net target PnL after costs
        net_pnl_target = dollar_target - total_cost
        net_pnl_risk = -(dollar_risk + total_cost)

        profile = RiskProfile(
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            position_size=position_size,
            direction=direction,
            tick_risk=tick_risk,
            tick_target=tick_target,
            dollar_risk=dollar_risk,
            dollar_target=dollar_target,
            risk_reward=risk_reward,
            slippage_cost=slippage_cost,
            commission_cost=commission_cost,
            total_cost=total_cost,
            net_pnl_target=net_pnl_target,
            net_pnl_risk=net_pnl_risk,
        )

        log.info(
            "risk_profile_computed",
            tick_risk=tick_risk,
            dollar_risk=dollar_risk,
            risk_reward=round(risk_reward, 2),
            total_cost=total_cost,
        )
        return profile

    # ------------------------------------------------------------------
    # Position sizing
    # ------------------------------------------------------------------

    def compute_position_size(
        self,
        request: PositionSizingRequest,
    ) -> int:
        """Compute the number of contracts based on risk budget.

        Parameters
        ----------
        request:
            Contains entry, stop, tick_size, tick_value, risk_budget,
            max_position_size, and is_event_window flag.

        Returns
        -------
        int
            Number of contracts (≥ 1).
        """
        log = logger.bind(
            entry=request.entry_price,
            stop=request.stop_price,
        )

        tick_risk = ticks_between(request.entry_price, request.stop_price, request.tick_size)

        if tick_risk <= 0:
            log.warning("zero_tick_risk", tick_risk=tick_risk)
            return 1

        dollar_per_tick = request.tick_value
        risk_per_contract = tick_risk * dollar_per_tick

        # Risk budget with optional event-window reduction
        effective_budget = request.risk_budget
        if request.is_event_window:
            event_reduction = getattr(request, "event_risk_reduction", 0.5)
            effective_budget *= event_reduction
            log.info(
                "event_window_reduction",
                original_budget=request.risk_budget,
                effective_budget=effective_budget,
                reduction_factor=event_reduction,
            )

        raw_size = effective_budget / risk_per_contract
        size = int(math.floor(raw_size))

        # Cap at max position size
        if request.max_position_size and size > request.max_position_size:
            size = request.max_position_size
            log.info("size_capped", max_position_size=request.max_position_size)

        final_size = max(1, size)
        log.info(
            "position_size_computed",
            tick_risk=tick_risk,
            risk_per_contract=risk_per_contract,
            raw_size=raw_size,
            final_size=final_size,
        )
        return final_size

    # ------------------------------------------------------------------
    # Ladder generation
    # ------------------------------------------------------------------

    def generate_ladder(
        self,
        entry_price: float,
        stop_price: float,
        target_price: float,
        total_size: int,
        num_levels: int,
        tick_size: float,
        direction: str,
    ) -> LadderPlan:
        """Generate a multi-level scaling ladder for entries, stops, and targets.

        Entry levels are spread around the base entry by ±tick increments.
        Stop levels graduate from tight to wide.
        Target levels are set at 1R, 2R, and 3R multiples.

        Parameters
        ----------
        entry_price, stop_price, target_price:
            Base trade levels.
        total_size:
            Total number of contracts to distribute.
        num_levels:
            Number of scale levels (2-5 recommended).
        tick_size:
            Minimum price increment.
        direction:
            ``"long"`` or ``"short"``.

        Returns
        -------
        LadderPlan
        """
        log = logger.bind(direction=direction, num_levels=num_levels)

        if num_levels < 1:
            num_levels = 1
        if total_size < num_levels:
            num_levels = total_size

        # Distribute contracts across levels (heavier at best price)
        sizes = self._distribute_contracts(total_size, num_levels)

        # Risk distance (in price)
        risk_distance = abs(entry_price - stop_price)
        target_distance = abs(target_price - entry_price)

        is_long = direction.lower() == "long"
        sign = 1.0 if is_long else -1.0

        levels: list[ScaleLevel] = []
        for i in range(num_levels):
            # Entry: spread around base entry
            # Level 0 = best entry, subsequent levels scale toward stop
            offset_ticks = i
            entry_offset = offset_ticks * tick_size * (-sign)
            level_entry = round_to_tick(entry_price + entry_offset, tick_size)

            # Stop: graduated from tight to wide
            # Level 0 = tightest, last level = base stop
            stop_fraction = 0.7 + (0.3 * i / max(num_levels - 1, 1))
            level_stop = round_to_tick(
                entry_price + (-sign * risk_distance * stop_fraction),
                tick_size,
            )

            # Target: T1 = 1R, T2 = 2R, T3 = 3R, etc.
            r_multiple = i + 1
            level_target = round_to_tick(
                entry_price + (sign * risk_distance * r_multiple),
                tick_size,
            )

            level = ScaleLevel(
                level=i + 1,
                entry_price=level_entry,
                stop_price=level_stop,
                target_price=level_target,
                size=sizes[i],
                r_multiple=float(r_multiple),
            )
            levels.append(level)

        ladder = LadderPlan(
            direction=direction,
            total_size=total_size,
            num_levels=num_levels,
            levels=levels,
            base_entry=entry_price,
            base_stop=stop_price,
            base_target=target_price,
        )

        log.info(
            "ladder_generated",
            total_size=total_size,
            levels_count=len(levels),
        )
        return ladder

    # ------------------------------------------------------------------
    # Round-trip cost
    # ------------------------------------------------------------------

    def compute_round_trip_cost(
        self,
        position_size: int,
        slippage_ticks: int,
        tick_value: float,
        commission_per_side: float,
    ) -> float:
        """Compute the total round-trip transaction cost.

        Returns
        -------
        float
            Total cost = slippage (round trip) + commissions (round trip).
        """
        slippage_cost = slippage_ticks * tick_value * position_size * 2
        commission_cost = commission_per_side * 2 * position_size
        total = slippage_cost + commission_cost
        logger.debug(
            "round_trip_cost",
            position_size=position_size,
            slippage_cost=slippage_cost,
            commission_cost=commission_cost,
            total=total,
        )
        return total

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _distribute_contracts(total: int, levels: int) -> list[int]:
        """Distribute contracts across *levels* with front-loading.

        The first level receives the most contracts, following a
        descending-weight pattern.
        """
        if levels == 1:
            return [total]

        # Weights: levels, levels-1, ..., 1
        weights = list(range(levels, 0, -1))
        weight_sum = sum(weights)

        sizes: list[int] = []
        allocated = 0
        for i, w in enumerate(weights):
            if i == len(weights) - 1:
                # Last level gets remainder
                sizes.append(total - allocated)
            else:
                portion = max(1, int(round(total * w / weight_sum)))
                if allocated + portion > total:
                    portion = total - allocated
                sizes.append(portion)
                allocated += portion

        # Ensure no zero sizes if total >= levels
        for i in range(len(sizes)):
            if sizes[i] <= 0 and allocated < total:
                sizes[i] = 1
                allocated += 1

        return sizes
