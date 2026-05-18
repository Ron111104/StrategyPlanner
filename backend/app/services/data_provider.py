"""
Data Provider — orchestrates data ingestion, caching, and spread computation.

Manages in-memory caches for market data, indicators, and snapshots.
Coordinates between QH adapter and internal engines.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.adapters.qh_adapter import QHAdapter
from app.contracts.market_data import (
    MarketDataFetchRequest,
    MarketDataIngest,
    MarketSnapshot,
    OHLCVBar,
    SpreadBar,
    Timeframe,
)
from app.core.logging import get_logger
from app.services.contract_registry import ContractRegistry
from app.utils.spread_helpers import compute_spread_series
from app.utils.validation_helpers import validate_bar_series, validate_product_match

logger = get_logger(__name__)


class DataProvider:
    """
    Central data provider with in-memory caching.

    Manages:
    - _bar_cache: product -> list[OHLCVBar]
    - _spread_cache: spread_symbol -> list[SpreadBar]
    - _latest_snapshots: spread_symbol -> MarketSnapshot
    """

    def __init__(
        self,
        qh_adapter: QHAdapter,
        contract_registry: ContractRegistry,
    ) -> None:
        self._adapter = qh_adapter
        self._registry = contract_registry

        # In-memory caches
        self._bar_cache: dict[str, list[OHLCVBar]] = {}
        self._spread_cache: dict[str, list[SpreadBar]] = {}
        self._latest_snapshots: dict[str, MarketSnapshot] = {}

        logger.info("data_provider_initialized")

    # ── Fetch from External API ───────────────────────────────

    async def fetch(self, request: MarketDataFetchRequest) -> dict[str, list[OHLCVBar]]:
        """
        Fetch OHLCV data from external API and cache.

        Validates data integrity after fetching.
        """
        logger.info(
            "fetching_market_data",
            products=request.products,
            timeframe=request.timeframe.value,
        )

        data = await self._adapter.fetch_ohlcv(
            products=request.products,
            timeframe=request.timeframe,
            bar_count=request.bar_count,
        )

        # Validate and cache each product
        for product, bars in data.items():
            warnings, errors = validate_bar_series(bars, min_bars=1)
            for w in warnings:
                logger.warning("data_warning", product=product, message=w.message)
            for e in errors:
                logger.error("data_error", product=product, message=e.message)

            if not errors:
                self._bar_cache[product] = bars
                logger.info("bars_cached", product=product, count=len(bars))

        # Auto-compute spreads for configured spread contracts
        await self._compute_cached_spreads(request.timeframe)

        return data

    # ── Manual Ingest ─────────────────────────────────────────

    async def ingest(self, ingest_data: MarketDataIngest) -> dict[str, Any]:
        """
        Manually ingest OHLCV bars into the cache.

        Validates data before caching.
        """
        product = ingest_data.product
        bars = ingest_data.bars

        validate_product_match(bars, product)
        warnings, errors = validate_bar_series(bars, min_bars=1)

        if errors:
            error_msgs = [e.message for e in errors]
            logger.error("ingest_validation_failed", product=product, errors=error_msgs)
            return {
                "status": "error",
                "product": product,
                "errors": error_msgs,
            }

        self._bar_cache[product] = bars
        logger.info("bars_ingested", product=product, count=len(bars))

        # Recompute affected spreads
        await self._compute_cached_spreads(ingest_data.timeframe)

        return {
            "status": "ok",
            "product": product,
            "bars_cached": len(bars),
            "warnings": [w.message for w in warnings],
        }

    # ── Getters ───────────────────────────────────────────────

    def get_bars(self, product: str) -> list[OHLCVBar]:
        """Get cached bars for a product."""
        return self._bar_cache.get(product, [])

    def get_spread_bars(self, spread_symbol: str) -> list[SpreadBar]:
        """Get cached spread bars."""
        return self._spread_cache.get(spread_symbol, [])

    def get_snapshot(self, spread_symbol: str) -> Optional[MarketSnapshot]:
        """Get latest market snapshot for a spread."""
        return self._latest_snapshots.get(spread_symbol)

    def get_all_snapshots(self) -> dict[str, MarketSnapshot]:
        """Get all cached market snapshots."""
        return dict(self._latest_snapshots)

    def get_cache_summary(self) -> dict[str, Any]:
        """Get summary of cached data."""
        return {
            "bar_cache": {k: len(v) for k, v in self._bar_cache.items()},
            "spread_cache": {k: len(v) for k, v in self._spread_cache.items()},
            "snapshots": list(self._latest_snapshots.keys()),
        }

    # ── Spread Computation ────────────────────────────────────

    async def _compute_cached_spreads(self, timeframe: Timeframe) -> None:
        """Auto-compute spread bars for all configured spread contracts."""
        for spread_contract in self._registry.all_spreads():
            front_sym = spread_contract.front_contract
            back_sym = spread_contract.back_contract
            spread_sym = spread_contract.symbol

            front_bars = self._bar_cache.get(front_sym)
            back_bars = self._bar_cache.get(back_sym)

            if not front_bars or not back_bars:
                continue

            try:
                # Align by minimum length
                min_len = min(len(front_bars), len(back_bars))
                aligned_front = front_bars[-min_len:]
                aligned_back = back_bars[-min_len:]

                spread_bars = compute_spread_series(
                    aligned_front, aligned_back, spread_sym
                )
                self._spread_cache[spread_sym] = spread_bars

                # Build latest snapshot
                if aligned_front and aligned_back:
                    snapshot = MarketSnapshot.from_prices(
                        timestamp=aligned_front[-1].timestamp,
                        front_contract=front_sym,
                        back_contract=back_sym,
                        front_price=aligned_front[-1].close,
                        back_price=aligned_back[-1].close,
                        front_volume=aligned_front[-1].volume,
                        back_volume=aligned_back[-1].volume,
                        timeframe=timeframe,
                    )
                    self._latest_snapshots[spread_sym] = snapshot

                logger.info(
                    "spread_computed",
                    spread=spread_sym,
                    bars=len(spread_bars),
                )
            except Exception as e:
                logger.error(
                    "spread_computation_failed",
                    spread=spread_sym,
                    error=str(e),
                )

    def clear_cache(self, product: Optional[str] = None) -> None:
        """Clear cached data."""
        if product:
            self._bar_cache.pop(product, None)
            self._spread_cache.pop(product, None)
            self._latest_snapshots.pop(product, None)
        else:
            self._bar_cache.clear()
            self._spread_cache.clear()
            self._latest_snapshots.clear()
