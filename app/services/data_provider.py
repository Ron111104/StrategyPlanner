"""Data provider service orchestrating market data fetch, caching, and spread computation."""
from typing import Optional

import httpx

from app.adapters.qh_adapter import QHAdapter
from app.config.loader import get_product_config, get_allowed_contracts, get_allowed_spreads
from app.contracts.market_data import OHLCVSeries, MarketSnapshot, SpreadQuote
from app.contracts.responses import MarketDataResponse
from app.core.exceptions import ContractNotFoundError, MarketDataError
from app.core.logging import get_logger
from app.services.cache import CacheManager

logger = get_logger(__name__)


class DataProvider:
    """Orchestrates market data fetching, caching, and spread construction."""

    def __init__(self, client: Optional[httpx.AsyncClient] = None) -> None:
        self._adapter = QHAdapter(client=client)
        self._cache = CacheManager()

    async def fetch_market_data(
        self,
        product_key: str,
        symbols: list[str],
        timeframe: str,
    ) -> MarketDataResponse:
        """Fetch OHLCV for the requested symbols, cache results, compute spreads."""
        product = get_product_config(product_key)
        allowed_contracts = get_allowed_contracts(product_key)
        allowed_spreads = get_allowed_spreads(product_key)

        outright_symbols: list[str] = []
        spread_symbols: list[str] = []

        for sym in symbols:
            if "-" in sym:
                if sym in allowed_spreads:
                    spread_symbols.append(sym)
                else:
                    raise ContractNotFoundError(
                        f"Spread '{sym}' not in allowed spreads for {product_key}"
                    )
            else:
                if sym in allowed_contracts:
                    outright_symbols.append(sym)
                else:
                    raise ContractNotFoundError(
                        f"Contract '{sym}' not in allowed contracts for {product_key}"
                    )

        # Collect all legs needed (outrights + spread legs)
        all_legs: set[str] = set(outright_symbols)
        for spread in spread_symbols:
            front, back = spread.split("-")
            all_legs.add(front)
            all_legs.add(back)

        # Fetch all legs
        fetched = await self._adapter.fetch_multiple(
            symbols=list(all_legs),
            timeframe=timeframe,
            product_key=product_key,
        )

        # Cache results
        symbols_loaded: list[str] = []
        bars_per_symbol: dict[str, int] = {}
        errors: list[str] = []

        for sym, series in fetched.items():
            self._cache.set_ohlcv(sym, timeframe, series)
            symbols_loaded.append(sym)
            bars_per_symbol[sym] = series.length

        # Compute spread quotes
        spread_quotes: list[SpreadQuote] = []
        for spread_sym in spread_symbols:
            front_leg, back_leg = spread_sym.split("-")
            front_series = self._cache.get_ohlcv(front_leg, timeframe)
            back_series = self._cache.get_ohlcv(back_leg, timeframe)

            if front_series and back_series and front_series.latest and back_series.latest:
                front_price = front_series.latest.close
                back_price = back_series.latest.close
                spread_bp = SpreadQuote.compute_spread_bp(front_price, back_price)
                quote = SpreadQuote(
                    spread_symbol=spread_sym,
                    front_leg=front_leg,
                    back_leg=back_leg,
                    front_price=front_price,
                    back_price=back_price,
                    spread_bp=spread_bp,
                    product_key=product_key,
                )
                self._cache.set_spread(spread_sym, quote)
                spread_quotes.append(quote)
                symbols_loaded.append(spread_sym)
            else:
                errors.append(f"Could not compute spread for {spread_sym}: missing leg data")

        # Collect snapshots
        snapshots: list[MarketSnapshot] = []
        for sym in outright_symbols:
            snap = self._cache.get_snapshot(sym)
            if snap:
                snapshots.append(snap)

        return MarketDataResponse(
            success=len(errors) == 0,
            symbols_loaded=symbols_loaded,
            bars_per_symbol=bars_per_symbol,
            snapshots=snapshots,
            spread_quotes=spread_quotes,
            errors=errors,
        )

    def get_cached_ohlcv(self, symbol: str, timeframe: str) -> Optional[OHLCVSeries]:
        """Get cached OHLCV data."""
        return self._cache.get_ohlcv(symbol, timeframe)

    def get_cached_snapshot(self, symbol: str) -> Optional[MarketSnapshot]:
        """Get cached snapshot."""
        return self._cache.get_snapshot(symbol)
