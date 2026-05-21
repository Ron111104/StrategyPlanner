"""
QH Market Data Adapter.

Async adapter for fetching OHLCV market data from external APIs.
Handles retry logic, timeout, schema normalization, and error mapping.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx

from app.contracts.market_data import OHLCVBar, Timeframe
from app.core.exceptions import DataFetchError
from app.core.logging import get_logger

logger = get_logger(__name__)

_TIMEFRAME_MAP: dict[str, str] = {
    "1M": "1min",
    "5M": "5min",
    "15M": "15min",
    "1H": "1hour",
    "4H": "4hour",
    "1D": "1day",
}

_MAX_RETRIES: int = 3
_BASE_DELAY: float = 1.0
_DEFAULT_TIMEOUT: float = 30.0


class QHAdapter:
    """Async adapter for external market data API with retry and normalization."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        client: httpx.AsyncClient | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "User-Agent": "ZQ-StrategyPlanner/1.0",
            },
        )

    async def close(self) -> None:
        """Close the underlying HTTP client if we own it."""
        if self._owns_client and self._client:
            await self._client.aclose()
            logger.info("qh_adapter_closed")

    async def fetch_ohlcv(
        self,
        product: str,
        timeframe: str,
        limit: int = 200,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[OHLCVBar]:
        """
        Fetch OHLCV bars from the external market data API.

        Args:
            product: Contract symbol (e.g., 'FFN25').
            timeframe: Bar timeframe (e.g., '1H').
            limit: Maximum number of bars to fetch.
            start_time: Optional start time filter.
            end_time: Optional end time filter.

        Returns:
            List of normalized OHLCVBar objects.

        Raises:
            DataFetchError: On network, timeout, or API errors after retries.
        """
        tf_api = _TIMEFRAME_MAP.get(timeframe, timeframe)

        params: dict[str, Any] = {
            "symbol": product,
            "interval": tf_api,
            "limit": min(limit, 1000),
        }

        if start_time is not None:
            params["start"] = int(start_time.timestamp())
        if end_time is not None:
            params["end"] = int(end_time.timestamp())

        url = f"{self._base_url}/v1/ohlcv"

        logger.info(
            "fetch_ohlcv_request",
            product=product,
            timeframe=timeframe,
            limit=limit,
            url=url,
        )

        raw_bars = await self._request_with_retry("GET", url, params=params)
        bars = self._normalize_bars(raw_bars, product, timeframe)

        logger.info(
            "fetch_ohlcv_response",
            product=product,
            timeframe=timeframe,
            bars_count=len(bars),
        )

        return bars

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute HTTP request with exponential backoff retry."""
        last_error: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await self._client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_body,
                )

                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", _BASE_DELAY * attempt))
                    logger.warning(
                        "rate_limited",
                        attempt=attempt,
                        retry_after=retry_after,
                    )
                    await asyncio.sleep(retry_after)
                    continue

                response.raise_for_status()
                data = response.json()

                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get("data", data.get("bars", data.get("results", [data])))
                else:
                    return []

            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning(
                    "request_timeout",
                    attempt=attempt,
                    url=url,
                    error=str(exc),
                )

            except httpx.HTTPStatusError as exc:
                last_error = exc
                logger.error(
                    "http_error",
                    attempt=attempt,
                    url=url,
                    status_code=exc.response.status_code,
                    body=exc.response.text[:500],
                )
                if exc.response.status_code < 500:
                    raise DataFetchError(
                        message=f"API returned {exc.response.status_code}",
                        source="qh_adapter",
                        details={"status": exc.response.status_code, "body": exc.response.text[:500]},
                    )

            except httpx.RequestError as exc:
                last_error = exc
                logger.warning(
                    "request_error",
                    attempt=attempt,
                    url=url,
                    error=str(exc),
                )

            if attempt < _MAX_RETRIES:
                delay = _BASE_DELAY * (2 ** (attempt - 1))
                logger.info("retry_backoff", delay=delay, attempt=attempt)
                await asyncio.sleep(delay)

        raise DataFetchError(
            message=f"Failed after {_MAX_RETRIES} retries",
            source="qh_adapter",
            details={"url": url, "last_error": str(last_error)},
        )

    def _normalize_bars(
        self,
        raw_bars: list[dict[str, Any]],
        product: str,
        timeframe: str,
    ) -> list[OHLCVBar]:
        """Normalize raw API response into OHLCVBar objects."""
        bars: list[OHLCVBar] = []

        for raw in raw_bars:
            try:
                bar = self._normalize_bar(raw, product, timeframe)
                bars.append(bar)
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning(
                    "bar_normalization_failed",
                    raw=str(raw)[:200],
                    error=str(exc),
                )
                continue

        bars.sort(key=lambda b: b.timestamp)
        return bars

    def _normalize_bar(
        self,
        raw: dict[str, Any],
        product: str,
        timeframe: str,
    ) -> OHLCVBar:
        """Normalize a single raw bar into an OHLCVBar."""
        timestamp = self._parse_timestamp(
            raw.get("timestamp") or raw.get("time") or raw.get("t") or raw.get("date")
        )

        open_price = float(raw.get("open") or raw.get("o", 0))
        high_price = float(raw.get("high") or raw.get("h", 0))
        low_price = float(raw.get("low") or raw.get("l", 0))
        close_price = float(raw.get("close") or raw.get("c", 0))
        volume = int(float(raw.get("volume") or raw.get("v", 0)))

        # Ensure OHLC consistency
        high_price = max(high_price, open_price, close_price)
        low_price = min(low_price, open_price, close_price)

        return OHLCVBar(
            timestamp=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            timeframe=Timeframe(timeframe),
            product=product,
        )

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime:
        """Parse various timestamp formats into datetime."""
        if value is None:
            return datetime.now(timezone.utc)

        if isinstance(value, (int, float)):
            if value > 1e12:
                value = value / 1000
            return datetime.fromtimestamp(value, tz=timezone.utc)

        if isinstance(value, str):
            for fmt in (
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ):
                try:
                    dt = datetime.strptime(value, fmt)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except ValueError:
                    continue

        raise ValueError(f"Cannot parse timestamp: {value!r}")
