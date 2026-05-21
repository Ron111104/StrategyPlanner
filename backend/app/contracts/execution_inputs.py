"""Execution input contract models for ZQ Strategy Planning Platform.

Defines account configuration, risk profiles, scale levels, ladder plans,
and position sizing request models for the execution/risk engine.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class AccountConfig(BaseModel):
    """Trading account configuration for risk and position sizing."""

    model_config = {"frozen": True}

    account_size_usd: Annotated[float, Field(gt=0, description="Total account size in USD")]
    risk_per_trade_usd: Annotated[float, Field(gt=0, description="Risk per trade in USD")]
    max_risk_per_trade_usd: Annotated[float, Field(gt=0, description="Maximum risk per trade in USD")]
    max_position_size: Annotated[int, Field(gt=0, description="Maximum contracts per position")]
    slippage_ticks: Annotated[int, Field(ge=0, description="Expected slippage in ticks")]
    commission_per_side: Annotated[float, Field(ge=0, description="Commission per side in USD")]
    event_risk_reduction: Annotated[float, Field(ge=0, le=1, description="Risk reduction factor during events (0-1)")]

    @model_validator(mode="after")
    def validate_risk_limits(self) -> AccountConfig:
        """Ensure risk_per_trade_usd does not exceed max_risk_per_trade_usd."""
        if self.risk_per_trade_usd > self.max_risk_per_trade_usd:
            raise ValueError(
                f"risk_per_trade_usd ({self.risk_per_trade_usd}) must not exceed "
                f"max_risk_per_trade_usd ({self.max_risk_per_trade_usd})"
            )
        if self.risk_per_trade_usd > self.account_size_usd:
            raise ValueError(
                f"risk_per_trade_usd ({self.risk_per_trade_usd}) must not exceed "
                f"account_size_usd ({self.account_size_usd})"
            )
        return self


class RiskProfile(BaseModel):
    """Computed risk profile for a trade setup.

    Contains entry/stop/target prices, position size, dollar values,
    risk/reward ratio, and cost estimates.
    """

    model_config = {"frozen": True}

    entry_price: Annotated[float, Field(gt=0, description="Entry price")]
    stop_price: Annotated[float, Field(gt=0, description="Stop loss price")]
    target_price: Annotated[float, Field(gt=0, description="Profit target price")]
    position_size: Annotated[int, Field(gt=0, description="Number of contracts")]
    direction: Literal["long", "short"]
    tick_risk: Annotated[int, Field(ge=0, description="Number of ticks at risk")]
    dollar_risk: Annotated[float, Field(ge=0, description="Total dollar risk")]
    dollar_target: Annotated[float, Field(ge=0, description="Total dollar target profit")]
    risk_reward_ratio: Annotated[float, Field(ge=0, description="Reward-to-risk ratio")]
    slippage_cost: Annotated[float, Field(ge=0, description="Estimated slippage cost in USD")]
    commission_cost: Annotated[float, Field(ge=0, description="Total commission cost (both sides) in USD")]
    total_cost: Annotated[float, Field(ge=0, description="slippage_cost + commission_cost")]
    net_pnl_target: Annotated[float, Field(description="dollar_target - total_cost")]

    @model_validator(mode="after")
    def validate_direction_prices(self) -> RiskProfile:
        """Validate price relationships based on trade direction."""
        if self.direction == "long":
            if self.stop_price >= self.entry_price:
                raise ValueError(
                    f"For long trades, stop_price ({self.stop_price}) must be < "
                    f"entry_price ({self.entry_price})"
                )
            if self.target_price <= self.entry_price:
                raise ValueError(
                    f"For long trades, target_price ({self.target_price}) must be > "
                    f"entry_price ({self.entry_price})"
                )
        elif self.direction == "short":
            if self.stop_price <= self.entry_price:
                raise ValueError(
                    f"For short trades, stop_price ({self.stop_price}) must be > "
                    f"entry_price ({self.entry_price})"
                )
            if self.target_price >= self.entry_price:
                raise ValueError(
                    f"For short trades, target_price ({self.target_price}) must be < "
                    f"entry_price ({self.entry_price})"
                )
        return self


class ScaleLevel(BaseModel):
    """A single price level in a scaling/ladder plan."""

    model_config = {"frozen": True}

    price: Annotated[float, Field(gt=0, description="Price level")]
    size: Annotated[int, Field(gt=0, description="Number of contracts at this level")]
    label: Annotated[str, Field(min_length=1, description="Level label e.g. 'Scale 1', 'Scale 2'")]
    percentage: Annotated[float, Field(ge=0, le=1, description="Fraction of total position (0-1)")]


class LadderPlan(BaseModel):
    """A multi-level entry/stop/target scaling plan.

    Contains entry, stop, and target levels with computed aggregates.
    """

    entry_levels: list[ScaleLevel] = Field(..., min_length=1, description="Entry scale levels")
    stop_levels: list[ScaleLevel] = Field(..., min_length=1, description="Stop scale levels")
    target_levels: list[ScaleLevel] = Field(..., min_length=1, description="Target scale levels")
    total_size: Annotated[int, Field(gt=0, description="Total position size across all entry levels")]
    average_entry: Annotated[float, Field(gt=0, description="Volume-weighted average entry price")]
    average_stop: Annotated[float, Field(gt=0, description="Volume-weighted average stop price")]
    average_target: Annotated[float, Field(gt=0, description="Volume-weighted average target price")]

    @field_validator("entry_levels", "stop_levels", "target_levels")
    @classmethod
    def validate_percentages_sum(cls, v: list[ScaleLevel]) -> list[ScaleLevel]:
        """Ensure percentages across levels sum to approximately 1.0."""
        total_pct = sum(level.percentage for level in v)
        if not (0.99 <= total_pct <= 1.01):
            raise ValueError(
                f"Scale level percentages must sum to ~1.0, got {total_pct:.4f}"
            )
        return v

    @model_validator(mode="after")
    def validate_total_size(self) -> LadderPlan:
        """Ensure total_size matches the sum of entry level sizes."""
        entry_sum = sum(level.size for level in self.entry_levels)
        if entry_sum != self.total_size:
            raise ValueError(
                f"total_size ({self.total_size}) must equal sum of entry level sizes ({entry_sum})"
            )
        return self


class PositionSizingRequest(BaseModel):
    """Request to compute position size for a given setup."""

    model_config = {"frozen": True}

    account_config: AccountConfig
    entry_price: Annotated[float, Field(gt=0, description="Planned entry price")]
    stop_price: Annotated[float, Field(gt=0, description="Planned stop loss price")]
    contract_tick_size: Annotated[float, Field(gt=0, description="Contract tick size")]
    contract_tick_value: Annotated[float, Field(gt=0, description="Dollar value per tick")]
    is_spread: bool = False
    is_event_window: bool = False

    @model_validator(mode="after")
    def validate_entry_stop_different(self) -> PositionSizingRequest:
        """Entry and stop prices must be different."""
        if self.entry_price == self.stop_price:
            raise ValueError("entry_price and stop_price must be different")
        return self
