"""
Data provider for CME Fed Funds Futures (ZQ) Strategy Planning Platform.

Manages market data ingestion, caching, and snapshot generation.
Interfaces with the QHAdapter for live / historical data fetching.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from app.contracts.market_data import MarketSnapshot, OHLCVBar, Timeframe
from app.adapters.qh_adapter import QHAdapter
from app.config.settings import ContractRegistry, Settings
from app.core.exceptions import InvalidContractError
from app.utils.datetime_helpers import now_utc
from app.utils.spread_helpers import implied_rate_from_price, price_to_spread_bp
from app.utils.validation_helpers import validate_bars_minimum

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class DataProvider:
    """Manages market data ingestion, caching, and snapshot generation."""

    __slots__ = (
        "_latest_snapshots",
        "_bar_cache",
        "_adapter",
        "_settings",
        "_contract_registry",
    )

    def __init__(
        self,
        adapter: QHAdapter,
        settings: Settings,
        contract_registry: ContractRegistry,
    ) -> None:
        self._latest_snapshots: dict[str, MarketSnapshot] = {}
        # Cache key: (product, timeframe_str)
        self._bar_cache: dict[tuple[str, str], list[OHLCVBar]] = {}
        self._adapter = adapter
        self._settings = settings
        self._contract_registry = contract_registry

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    async def ingest_bars(
        self,
        product: str,
        timeframe: str,
        bars: list[OHLCVBar],
    ) -> int:
        """Store bars in cache and update snapshot.

        Parameters
        ----------
        product:
            Product symbol, e.g. ``"ZQM2026"``.
        timeframe:
            Timeframe string, e.g. ``"5m"``, ``"1h"``, ``"1d"``.
        bars:
            OHLCV bar list sorted chronologically.

        Returns
        -------
        int
            Number of bars stored.
        """
        if not bars:
            logger.warning("ingest_bars_empty", product=product, timeframe=timeframe)
            return 0

        self._validate_product(product)

        cache_key = (product, timeframe)
        existing = self._bar_cache.get(cache_key, [])

        # Deduplicate by timestamp — merge new bars onto existing
        existing_timestamps: set[datetime] = {b.timestamp for b in existing}
        new_bars = [b for b in bars if b.timestamp not in existing_timestamps]

        merged = sorted(existing + new_bars, key=lambda b: b.timestamp)
        self._bar_cache[cache_key] = merged

        # Update snapshot from latest bar
        self._update_snapshot(product, merged)

        logger.info(
            "bars_ingested",
            product=product,
            timeframe=timeframe,
            new_bars=len(new_bars),
            total_bars=len(merged),
        )
        return len(new_bars)

    # ------------------------------------------------------------------
    # Fetch (via adapter)
    # ------------------------------------------------------------------

    async def fetch_bars(
        self,
        product: str,
        timeframe: str,
        limit: int = 200,
    ) -> list[OHLCVBar]:
        """Fetch bars from the upstream adapter, normalise, store, and return.

        Parameters
        ----------
        product:
            Product symbol.
        timeframe:
            Timeframe string.
        limit:
            Max number of bars to request.

        Returns
        -------
        list[OHLCVBar]
            Fetched and cached bars.

        Raises
        ------
        InvalidContractError
            If *product* is not in the contract registry.
        """
        self._validate_product(product)
        log = logger.bind(product=product, timeframe=timeframe, limit=limit)

        try:
            raw_bars: list[OHLCVBar] = await self._adapter.fetch_bars(
                product=product,
                timeframe=timeframe,
                limit=limit,
            )
        except Exception as exc:
            log.error("adapter_fetch_failed", error=str(exc))
            raise

        if not raw_bars:
            log.warning("adapter_returned_no_bars")
            return []

        # Normalise: sort chronologically
        raw_bars.sort(key=lambda b: b.timestamp)

        # Store
        await self.ingest_bars(product, timeframe, raw_bars)

        log.info("bars_fetched", count=len(raw_bars))
        return raw_bars

    # ------------------------------------------------------------------
    # Retrieval (cache only)
    # ------------------------------------------------------------------

    async def get_bars(
        self,
        product: str,
        timeframe: str,
    ) -> list[OHLCVBar] | None:
        """Return cached bars for *product* / *timeframe*, or ``None``."""
        cache_key = (product, timeframe)
        bars = self._bar_cache.get(cache_key)
        if bars is None:
            logger.debug("cache_miss", product=product, timeframe=timeframe)
        return bars

    async def get_snapshot(self, product: str) -> MarketSnapshot | None:
        """Return the latest market snapshot for *product*, or ``None``."""
        return self._latest_snapshots.get(product)

    # ------------------------------------------------------------------
    # Spread snapshot
    # ------------------------------------------------------------------

    async def compute_spread_snapshot(
        self,
        front_product: str,
        back_product: str,
    ) -> MarketSnapshot:
        """Compute a spread snapshot between front and back month.

        Parameters
        ----------
        front_product:
            Front-month contract symbol.
        back_product:
            Back-month (deferred) contract symbol.

        Returns
        -------
        MarketSnapshot
            Synthetic spread snapshot with spread_bp computed.

        Raises
        ------
        InvalidContractError
            If either product is unknown or has no snapshot.
        """
        front_snap = self._latest_snapshots.get(front_product)
        back_snap = self._latest_snapshots.get(back_product)

        if front_snap is None:
            raise InvalidContractError(
                f"No snapshot available for front product '{front_product}'"
            )
        if back_snap is None:
            raise InvalidContractError(
                f"No snapshot available for back product '{back_product}'"
            )

        spread_price = front_snap.last_price - back_snap.last_price
        spread_bp = price_to_spread_bp(front_snap.last_price, back_snap.last_price)

        front_rate = implied_rate_from_price(front_snap.last_price)
        back_rate = implied_rate_from_price(back_snap.last_price)
        rate_spread_bp = (back_rate - front_rate) * 10_000  # rate differential in bp

        spread_snapshot = MarketSnapshot(
            product=f"{front_product}-{back_product}",
            last_price=spread_price,
            bid=front_snap.bid - back_snap.ask if front_snap.bid and back_snap.ask else None,
            ask=front_snap.ask - back_snap.bid if front_snap.ask and back_snap.bid else None,
            volume=(front_snap.volume or 0) + (back_snap.volume or 0),
            open_interest=None,
            timestamp=now_utc(),
            spread_bp=spread_bp,
            implied_rate_front=front_rate,
            implied_rate_back=back_rate,
        )

        logger.info(
            "spread_snapshot_computed",
            front=front_product,
            back=back_product,
            spread_price=spread_price,
            spread_bp=spread_bp,
            rate_spread_bp=rate_spread_bp,
        )
        return spread_snapshot

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_snapshot(self, product: str, bars: list[OHLCVBar]) -> None:
        """Create a ``MarketSnapshot`` from the latest bar and store it."""
        if not bars:
            return

        latest = bars[-1]
        implied_rate = implied_rate_from_price(latest.close)

        snapshot = MarketSnapshot(
            product=product,
            last_price=latest.close,
            bid=None,  # bar data doesn't have bid/ask
            ask=None,
            volume=latest.volume,
            open_interest=None,
            timestamp=latest.timestamp,
            high=latest.high,
            low=latest.low,
            open=latest.open,
            close=latest.close,
            implied_rate=implied_rate,
        )
        self._latest_snapshots[product] = snapshot
        logger.debug(
            "snapshot_updated",
            product=product,
            last_price=latest.close,
            implied_rate=implied_rate,
        )

    def _validate_product(self, product: str) -> None:
        """Raise ``InvalidContractError`` if product is unknown."""
        if not self._contract_registry.is_valid(product):
            raise InvalidContractError(
                f"Product '{product}' is not in the contract registry"
            )
