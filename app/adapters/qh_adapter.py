"""External market data API adapter."""
from datetime import datetime
from typing import Any, Optional

import httpx

from app.contracts.market_data import OHLCVBar, OHLCVSeries
from app.core.exceptions import AdapterError, MarketDataError
from app.core.logging import get_logger
from app.core.settings import get_settings

logger = get_logger(__name__)

TIMEFRAME_MAP: dict[str, str] = {
    "1M": "1min",
    "5M": "5min",
    "15M": "15min",
    "1H": "1hour",
    "4H": "4hour",
    "1D": "1day",
}


class QHAdapter:
    """Adapter for fetching OHLCV data from the external API."""

    def __init__(self, client: Optional[httpx.AsyncClient] = None) -> None:
        self._settings = get_settings()
        self._client = client
        self._base_url = self._settings.QH_API_BASE_URL.rstrip("/")
        self._api_key = self._settings.QH_API_KEY

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(
            timeout=httpx.Timeout(self._settings.QH_API_TIMEOUT),
            headers=self._build_headers(),
        )

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _map_timeframe(self, timeframe: str) -> str:
        mapped = TIMEFRAME_MAP.get(timeframe)
        if not mapped:
            raise AdapterError(
                f"Unsupported timeframe: {timeframe}. "
                f"Supported: {list(TIMEFRAME_MAP.keys())}"
            )
        return mapped

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        product_key: str = "",
        limit: Optional[int] = None,
    ) -> OHLCVSeries:
        """Fetch OHLCV bars for a single symbol."""
        mapped_tf = self._map_timeframe(timeframe)
        params: dict[str, Any] = {
            "products": symbol,
            "timeIntervals": mapped_tf,
        }
        if limit:
            params["limit"] = min(limit, self._settings.MAX_BARS_PER_REQUEST)

        url = f"{self._base_url}/api/ohlc/"
        client = await self._get_client()
        owns_client = self._client is None

        try:
            logger.info("fetching_ohlcv", symbol=symbol, timeframe=timeframe, url=url)
            response = await client.get(url, params=params, headers=self._build_headers())
            response.raise_for_status()
            raw_data = response.json()
            bars = self._parse_bars(raw_data)
            logger.info("ohlcv_fetched", symbol=symbol, bars_count=len(bars))
            return OHLCVSeries(
                symbol=symbol,
                timeframe=timeframe,
                bars=bars,
                product_key=product_key,
            )
        except httpx.HTTPStatusError as e:
            raise MarketDataError(
                f"HTTP {e.response.status_code} fetching {symbol}: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise MarketDataError(f"Request error fetching {symbol}: {str(e)}")
        except Exception as e:
            raise MarketDataError(f"Unexpected error fetching {symbol}: {str(e)}")
        finally:
            if owns_client:
                await client.aclose()

    async def fetch_multiple(
        self,
        symbols: list[str],
        timeframe: str,
        product_key: str = "",
    ) -> dict[str, OHLCVSeries]:
        """Fetch OHLCV for multiple symbols."""
        results: dict[str, OHLCVSeries] = {}
        for symbol in symbols:
            try:
                series = await self.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    product_key=product_key,
                )
                results[symbol] = series
            except MarketDataError as e:
                logger.error("fetch_failed", symbol=symbol, error=str(e))
        return results

    def _parse_bars(self, raw_data: Any) -> list[OHLCVBar]:
        """Parse raw API response into OHLCVBar list."""
        bars: list[OHLCVBar] = []
        if isinstance(raw_data, list):
            items = raw_data
        elif isinstance(raw_data, dict):
            items = raw_data.get("data", raw_data.get("bars", raw_data.get("results", [])))
            if not isinstance(items, list):
                items = []
        else:
            return bars

        for item in items:
            try:
                bar = OHLCVBar(
                    timestamp=self._parse_timestamp(item.get("Timestamp", item.get("timestamp", item.get("t", "")))),
                    open=float(item.get("Open", item.get("open", item.get("o", 0)))),
                    high=float(item.get("High", item.get("high", item.get("h", 0)))),
                    low=float(item.get("Low", item.get("low", item.get("l", 0)))),
                    close=float(item.get("Close", item.get("close", item.get("c", 0)))),
                    volume=float(item.get("Volume", item.get("volume", item.get("v", 0)))),
                )
                bars.append(bar)
            except (ValueError, TypeError) as e:
                logger.warning("bar_parse_error", error=str(e), raw=str(item)[:200])
                continue
        return bars

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime:
        """Parse various timestamp formats."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            if value > 1e12:
                return datetime.utcfromtimestamp(value / 1000)
            return datetime.utcfromtimestamp(value)
        if isinstance(value, str):
            for fmt in (
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
        raise ValueError(f"Cannot parse timestamp: {value}")
