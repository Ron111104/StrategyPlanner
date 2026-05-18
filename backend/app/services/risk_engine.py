"""
Risk Engine — planning-only risk computation, sizing, and ladder generation.

NOT for order submission or execution routing.
Computes stop distances, dollar risk, commissions, slippage, and R:R ratios.
"""

from __future__ import annotations

import math
from typing import Any, Optional

from app.contracts.execution_inputs import (
    AccountConfig,
    LadderPlan,
    RiskCalcInput,
    RiskCalcResult,
    ScaleLevel,
)
from app.contracts.market_data import ContractType
from app.core.logging import get_logger
from app.utils.math_helpers import (
    compute_max_lots,
    compute_rr_ratio,
    price_to_ticks,
    ticks_to_dollars,
)

logger = get_logger(__name__)


class RiskEngine:
    """
    Institutional risk computation engine for strategy planning.

    Supports volatility-adjusted sizing, event risk reduction,
    ladder planning, and complete round-trip cost modeling.
    """

    def __init__(self, settings: dict[str, Any]) -> None:
        risk_cfg = settings.get("risk", {})
        sizing_cfg = settings.get("sizing", {})

        self._account = AccountConfig(
            max_risk_per_trade=risk_cfg.get("max_risk_per_trade", 500.0),
            max_lots=risk_cfg.get("max_lots", 20),
            max_daily_risk=risk_cfg.get("max_daily_risk", 2500.0),
            event_risk_multiplier=risk_cfg.get("event_risk_multiplier", 0.5),
            default_slippage_ticks=risk_cfg.get("default_slippage_ticks", 1),
            default_commission_per_lot=risk_cfg.get("default_commission_per_lot", 2.50),
        )

        self._scale_levels: int = sizing_cfg.get("scale_in_levels", 3)
        self._scale_ratios: list[float] = sizing_cfg.get("scale_in_ratios", [0.5, 0.3, 0.2])
        self._target_levels: int = sizing_cfg.get("target_levels", 3)
        self._target_ratios: list[float] = sizing_cfg.get("target_ratios", [0.5, 0.3, 0.2])

        logger.info("risk_engine_initialized", max_risk=self._account.max_risk_per_trade)

    @property
    def account_config(self) -> AccountConfig:
        return self._account

    def update_account(self, config: AccountConfig) -> None:
        """Update account configuration."""
        self._account = config
        logger.info("account_config_updated", max_risk=config.max_risk_per_trade)

    def compute_risk(self, input_data: RiskCalcInput, targets: list[float] | None = None) -> RiskCalcResult:
        """Compute complete risk profile for a planned trade."""
        # Stop distance in ticks
        stop_distance_price = abs(input_data.entry_price - input_data.stop_price)
        stop_ticks = price_to_ticks(stop_distance_price, input_data.tick_size)

        # Dollar risk per lot
        dollar_risk_per_lot = ticks_to_dollars(stop_ticks, input_data.tick_value)

        # Effective max risk (event-adjusted)
        effective_max_risk = input_data.custom_max_risk or self._account.max_risk_per_trade
        event_adjusted = False
        if input_data.is_event_regime:
            effective_max_risk *= self._account.event_risk_multiplier
            event_adjusted = True

        # Max lots
        max_lots_computed = compute_max_lots(effective_max_risk, stop_ticks, input_data.tick_value)
        max_lots_cap = input_data.custom_max_lots or self._account.max_lots
        max_lots = min(max_lots_computed, max_lots_cap)

        # Costs
        commission_per_lot = self._account.default_commission_per_lot
        total_commission = commission_per_lot * max_lots * 2  # round trip
        slippage_per_lot = ticks_to_dollars(
            self._account.default_slippage_ticks, input_data.tick_value
        )
        total_slippage = slippage_per_lot * max_lots * 2  # round trip
        total_risk = dollar_risk_per_lot * max_lots
        round_trip_cost = total_commission + total_slippage

        # R:R ratio
        rr: Optional[float] = None
        if targets and len(targets) > 0:
            rr = compute_rr_ratio(input_data.entry_price, input_data.stop_price, targets[0])

        # Caution flags
        caution_flags: list[str] = []
        if max_lots == 0:
            caution_flags.append("Zero lots: risk too small for stop distance")
        if stop_ticks < 2:
            caution_flags.append("Stop distance very tight (<2 ticks)")
        if total_risk > self._account.max_daily_risk * 0.5:
            caution_flags.append("Trade risk exceeds 50% of daily limit")
        if event_adjusted:
            caution_flags.append("Risk reduced for event regime")

        return RiskCalcResult(
            stop_distance_ticks=round(stop_ticks, 2),
            stop_distance_price=round(stop_distance_price, 6),
            dollar_risk_per_lot=round(dollar_risk_per_lot, 2),
            max_lots=max_lots,
            total_risk=round(total_risk, 2),
            commission_per_lot=round(commission_per_lot, 2),
            total_commission=round(total_commission, 2),
            slippage_per_lot=round(slippage_per_lot, 2),
            total_slippage=round(total_slippage, 2),
            round_trip_cost=round(round_trip_cost, 2),
            risk_reward_ratio=rr,
            effective_max_risk=round(effective_max_risk, 2),
            event_adjusted=event_adjusted,
            caution_flags=caution_flags,
        )

    def build_ladder(
        self,
        entry_price: float,
        stop_price: float,
        targets: list[float],
        total_lots: int,
        tick_size: float,
        tick_value: float,
        direction: str = "long",
    ) -> LadderPlan:
        """Build a complete entry/exit ladder plan."""
        if total_lots <= 0:
            return LadderPlan(
                stop_price=stop_price,
                total_lots=0,
                total_risk=0,
                average_entry=entry_price,
            )

        # Entry scale levels
        entry_levels: list[ScaleLevel] = []
        is_long = direction.lower() == "long"

        for i, ratio in enumerate(self._scale_ratios[: self._scale_levels]):
            lots = max(1, math.floor(total_lots * ratio))
            if is_long:
                level_price = entry_price - (i * tick_size * 2)
            else:
                level_price = entry_price + (i * tick_size * 2)

            stop_dist = abs(level_price - stop_price)
            dollar_risk = price_to_ticks(stop_dist, tick_size) * tick_value * lots

            entry_levels.append(ScaleLevel(
                level_index=i,
                price=round(level_price, 6),
                lots=lots,
                ratio=ratio,
                dollar_risk=round(dollar_risk, 2),
                description=f"Scale {i + 1}: {lots} lots @ {level_price:.3f}",
            ))

        # Target scale levels
        target_levels: list[ScaleLevel] = []
        for i, (target, ratio) in enumerate(
            zip(targets[: self._target_levels], self._target_ratios[: self._target_levels])
        ):
            lots = max(1, math.floor(total_lots * ratio))
            target_levels.append(ScaleLevel(
                level_index=i,
                price=round(target, 6),
                lots=lots,
                ratio=ratio,
                dollar_risk=0,
                description=f"Target {i + 1}: {lots} lots @ {target:.3f}",
            ))

        # Weighted average entry
        total_entry_lots = sum(l.lots for l in entry_levels)
        avg_entry = (
            sum(l.price * l.lots for l in entry_levels) / total_entry_lots
            if total_entry_lots > 0
            else entry_price
        )

        total_risk = sum(l.dollar_risk for l in entry_levels)
        rr = compute_rr_ratio(avg_entry, stop_price, targets[0]) if targets else None

        return LadderPlan(
            entry_levels=entry_levels,
            target_levels=target_levels,
            stop_price=stop_price,
            total_lots=total_entry_lots,
            total_risk=round(total_risk, 2),
            average_entry=round(avg_entry, 6),
            risk_reward_ratio=rr,
        )
