"""
QH (Quant Hub) API Adapter — external data translation layer.

This adapter is the ONLY module that understands the external QH API schema.
External schemas NEVER leak past this adapter into engine internals.

Responsibilities:
- HTTP communication with QH API
- Schema normalization to internal contracts
- Retry handling and timeout management
- Response validation and error translation
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.config.settings import QHApiSettings
from app.contracts.external_api import ExternalAPIError, QHOHLCCandle, QHOHLCProductResponse, QHOHLCResponse
from app.contracts.market_data import OHLCVBar, Timeframe
from app.core.logging import get_logger

logger = get_logger(__name__)


class QHAdapterError(Exception):
    """Raised when QH API communication fails."""

    def __init__(self, message: str, error: Optional[ExternalAPIError] = None):
        self.message = message
        self.error = error
        super().__init__(message)


class QHAdapter:
    """
    Adapter for Quant Hub OHLCV API.

    Translates external QH API responses to internal OHLCVBar contracts.
    Handles retries, timeouts, and schema normalization.
    """

    MAX_RETRIES = 3
    RETRY_BACKOFF_SECONDS = 1.0

    def __init__(self, settings: QHApiSettings) -> None:
        self._settings = settings
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._settings.base_url,
                timeout=httpx.Timeout(self._settings.timeout_seconds),
                headers=self._build_headers(),
            )
        return self._client

    def _build_headers(self) -> dict[str, str]:
        """Build request headers with Bearer auth."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self._settings.api_token:
            headers["Authorization"] = f"Bearer {self._settings.api_token}"
        return headers

    async def fetch_ohlcv(
        self,
        products: list[str],
        timeframe: Timeframe,
        bar_count: Optional[int] = None,
    ) -> dict[str, list[OHLCVBar]]:
        """
        Fetch OHLCV data from QH API and normalize to internal contracts.

        Args:
            products: List of product symbols to fetch
            timeframe: Desired timeframe
            bar_count: Optional number of bars to request

        Returns:
            Dict mapping product symbol to list of normalized OHLCVBar

        Raises:
            QHAdapterError: On communication or validation failure
        """
        logger.info(
            "fetching_ohlcv",
            products=products,
            timeframe=timeframe.value,
            bar_count=bar_count,
        )

        params = self._build_params(products, timeframe, bar_count)
        raw_response = await self._execute_request(params)
        parsed = self._parse_response(raw_response)
        normalized = self._normalize_response(parsed, timeframe)

        logger.info(
            "ohlcv_fetched",
            products=list(normalized.keys()),
            bar_counts={k: len(v) for k, v in normalized.items()},
        )

        return normalized

    def _build_params(
        self,
        products: list[str],
        timeframe: Timeframe,
        bar_count: Optional[int],
    ) -> dict[str, str]:
        """Build query parameters for QH API request."""
        params: dict[str, str] = {
            "products": ",".join(products),
            "timeIntervals": timeframe.value,
        }
        if bar_count is not None:
            params["limit"] = str(bar_count)
        return params

    async def _execute_request(
        self,
        params: dict[str, str],
    ) -> dict[str, Any]:
        """
        Execute HTTP GET with retry logic.

        Returns raw JSON response dict.
        """
        client = await self._get_client()
        last_error: Optional[Exception] = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = await client.get(
                    self._settings.ohlc_endpoint,
                    params=params,
                )

                if response.status_code != 200:
                    error = ExternalAPIError(
                        source="QH_API",
                        status_code=response.status_code,
                        message=f"HTTP {response.status_code}",
                        raw_response=response.text[:500],
                    )
                    raise QHAdapterError(
                        f"QH API returned {response.status_code}",
                        error=error,
                    )

                return response.json()

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    "qh_api_timeout",
                    attempt=attempt,
                    max_retries=self.MAX_RETRIES,
                )
                if attempt < self.MAX_RETRIES:
                    import asyncio
                    await asyncio.sleep(self.RETRY_BACKOFF_SECONDS * attempt)

            except httpx.HTTPError as e:
                last_error = e
                logger.error(
                    "qh_api_http_error",
                    attempt=attempt,
                    error=str(e),
                )
                if attempt < self.MAX_RETRIES:
                    import asyncio
                    await asyncio.sleep(self.RETRY_BACKOFF_SECONDS * attempt)

        raise QHAdapterError(
            f"QH API request failed after {self.MAX_RETRIES} retries: {last_error}"
        )

    def _parse_response(self, raw: dict[str, Any]) -> QHOHLCResponse:
        """Parse raw JSON into external API contract."""
        try:
            return QHOHLCResponse.model_validate(raw)
        except Exception as e:
            raise QHAdapterError(f"Failed to parse QH API response: {e}")

    def _normalize_response(
        self,
        response: QHOHLCResponse,
        timeframe: Timeframe,
    ) -> dict[str, list[OHLCVBar]]:
        """
        Normalize external QH response to internal OHLCVBar contracts.

        - Reverses newest-first ordering to oldest-first
        - Maps external schema fields to internal contract fields
        - Validates candle structure
        """
        result: dict[str, list[OHLCVBar]] = {}

        for product_data in response.data:
            bars: list[OHLCVBar] = []

            # QH API returns newest first — reverse to oldest first
            candles = list(reversed(product_data.candles))

            for candle in candles:
                try:
                    bar = self._candle_to_bar(candle, product_data.product, timeframe)
                    bars.append(bar)
                except Exception as e:
                    logger.warning(
                        "candle_normalization_skipped",
                        product=product_data.product,
                        timestamp=str(candle.t),
                        error=str(e),
                    )

            if bars:
                result[product_data.product] = bars
            else:
                logger.warning(
                    "empty_product_data",
                    product=product_data.product,
                )

        return result

    @staticmethod
    def _candle_to_bar(
        candle: QHOHLCCandle,
        product: str,
        timeframe: Timeframe,
    ) -> OHLCVBar:
        """Convert a single external candle to internal OHLCVBar."""
        timestamp = candle.t
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        return OHLCVBar(
            timestamp=timestamp,
            open=candle.o,
            high=candle.h,
            low=candle.l,
            close=candle.c,
            volume=candle.v,
            timeframe=timeframe,
            product=product,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
