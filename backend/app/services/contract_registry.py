"""
Contract Registry — dynamic contract loading from YAML configuration.

Provides typed access to all configured outright and spread contracts.
NO hardcoded instruments — everything is loaded from contracts.yaml.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from app.contracts.market_data import ContractType
from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Contract Definitions ─────────────────────────────────────

class OutrightContract(BaseModel):
    """Configured outright contract from YAML."""
    symbol: str
    type: ContractType = ContractType.OUTRIGHT
    description: str = ""
    tick_size: float = Field(default=0.005, gt=0)
    tick_value: float = Field(default=20.835, gt=0)
    contract_value: float = Field(default=4167, gt=0)
    expiry: Optional[str] = None


class SpreadContract(BaseModel):
    """Configured spread contract from YAML."""
    symbol: str
    type: ContractType = ContractType.SPREAD
    description: str = ""
    front_contract: str
    back_contract: str
    tick_size_bp: float = Field(default=0.5, gt=0)
    tick_value: float = Field(default=20.835, gt=0)


class ContractRegistry:
    """
    Dynamic contract registry loaded from YAML configuration.

    Provides lookup for all configured outrights and spreads.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._outrights: dict[str, OutrightContract] = {}
        self._spreads: dict[str, SpreadContract] = {}
        self._load_contracts(config)

    def _load_contracts(self, config: dict[str, Any]) -> None:
        """Parse YAML config and populate registries."""
        contracts = config.get("contracts", [])

        for entry in contracts:
            contract_type = entry.get("type", "outright")

            if contract_type == "outright":
                contract = OutrightContract(**entry)
                self._outrights[contract.symbol] = contract
                logger.info("contract_registered", symbol=contract.symbol, type="outright")

            elif contract_type == "spread":
                contract = SpreadContract(**entry)
                self._spreads[contract.symbol] = contract
                logger.info("contract_registered", symbol=contract.symbol, type="spread")

            else:
                logger.warning("unknown_contract_type", type=contract_type, entry=entry)

        logger.info(
            "contract_registry_loaded",
            outrights=len(self._outrights),
            spreads=len(self._spreads),
        )

    # ── Lookups ───────────────────────────────────────────────

    def get_outright(self, symbol: str) -> Optional[OutrightContract]:
        """Get an outright contract by symbol."""
        return self._outrights.get(symbol)

    def get_spread(self, symbol: str) -> Optional[SpreadContract]:
        """Get a spread contract by symbol."""
        return self._spreads.get(symbol)

    def get_contract_type(self, symbol: str) -> Optional[ContractType]:
        """Determine the contract type for a symbol."""
        if symbol in self._outrights:
            return ContractType.OUTRIGHT
        if symbol in self._spreads:
            return ContractType.SPREAD
        return None

    def get_tick_size(self, symbol: str) -> Optional[float]:
        """Get tick size for any contract type."""
        outright = self._outrights.get(symbol)
        if outright:
            return outright.tick_size
        spread = self._spreads.get(symbol)
        if spread:
            return spread.tick_size_bp
        return None

    def get_tick_value(self, symbol: str) -> Optional[float]:
        """Get tick value for any contract type."""
        outright = self._outrights.get(symbol)
        if outright:
            return outright.tick_value
        spread = self._spreads.get(symbol)
        if spread:
            return spread.tick_value
        return None

    def all_outrights(self) -> list[OutrightContract]:
        """Get all configured outrights."""
        return list(self._outrights.values())

    def all_spreads(self) -> list[SpreadContract]:
        """Get all configured spreads."""
        return list(self._spreads.values())

    def all_symbols(self) -> list[str]:
        """Get all configured symbols."""
        return list(self._outrights.keys()) + list(self._spreads.keys())

    def is_registered(self, symbol: str) -> bool:
        """Check if a symbol is registered."""
        return symbol in self._outrights or symbol in self._spreads

    def get_spread_legs(self, symbol: str) -> Optional[tuple[str, str]]:
        """Get front/back leg symbols for a spread."""
        spread = self._spreads.get(symbol)
        if spread:
            return (spread.front_contract, spread.back_contract)
        return None

    def to_dict(self) -> dict[str, Any]:
        """Serialize registry to dict for API responses."""
        return {
            "outrights": [c.model_dump() for c in self._outrights.values()],
            "spreads": [c.model_dump() for c in self._spreads.values()],
            "total_count": len(self._outrights) + len(self._spreads),
        }
