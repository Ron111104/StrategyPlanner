# Market Data Documentation

> QH API integration, OHLCV fetching, timeframe mapping, spread generation, caching, and normalization.

---

## 1. Overview

The market data pipeline fetches OHLCV candlestick data from an external API (referred to as "QH API"), normalizes it into typed Pydantic models, caches it in memory, and optionally computes indicators. The pipeline is fully async.

### Components

| Component | File | Role |
|---|---|---|
| `QHAdapter` | `app/adapters/qh_adapter.py` | HTTP client for external API |
| `DataProvider` | `app/services/data_provider.py` | Orchestration: fetch → cache → spread compute |
| `CacheManager` | `app/services/cache.py` | In-memory storage |
| Route handlers | `app/routes/market_data.py` | API endpoints |

---

## 2. QH API Integration

### Adapter Architecture

`QHAdapter` encapsulates all external API communication:

```python
class QHAdapter:
    def __init__(self, client: Optional[httpx.AsyncClient]) -> None
    async def fetch_ohlcv(self, symbol, timeframe, product_key, limit) -> OHLCVSeries
    async def fetch_multiple(self, symbols, timeframe, product_key) -> dict[str, OHLCVSeries]
```

### URL Construction

```
{QH_API_BASE_URL}/api/ohlc/?products={symbol}&timeIntervals={mapped_tf}
```

### Authentication

If `QH_API_KEY` is set in `.env`, it is sent as:
```
Authorization: Bearer {QH_API_KEY}
```

### Timeframe Mapping

The platform uses short timeframe codes internally. The adapter maps them to API-expected formats:

| Internal | API Format |
|---|---|
| `1M` | `1min` |
| `5M` | `5min` |
| `15M` | `15min` |
| `1H` | `1hour` |
| `4H` | `4hour` |
| `1D` | `1day` |

Unsupported timeframes raise `AdapterError`.

---

## 3. Response Parsing

The adapter handles multiple response formats:

### Response Structure

The adapter tries three wrapper formats:
```python
# List format
[{bar}, {bar}, ...]

# Dict format with various keys
{"data": [{bar}, ...]}
{"bars": [{bar}, ...]}
{"results": [{bar}, ...]}
```

### Field Name Resolution

Each OHLCV field tries multiple key names:

| Field | Tried Keys |
|---|---|
| Timestamp | `Timestamp`, `timestamp`, `t` |
| Open | `Open`, `open`, `o` |
| High | `High`, `high`, `h` |
| Low | `Low`, `low`, `l` |
| Close | `Close`, `close`, `c` |
| Volume | `Volume`, `volume`, `v` |

### Timestamp Parsing

The adapter parses six timestamp formats:

```python
# datetime object — used directly
# Unix seconds (< 1e12)
datetime.utcfromtimestamp(value)
# Unix milliseconds (>= 1e12)
datetime.utcfromtimestamp(value / 1000)
# ISO 8601 variants
"%Y-%m-%dT%H:%M:%S"
"%Y-%m-%dT%H:%M:%SZ"
"%Y-%m-%dT%H:%M:%S.%f"
"%Y-%m-%dT%H:%M:%S.%fZ"
"%Y-%m-%d %H:%M:%S"
"%Y-%m-%d"
```

### Error Handling

- HTTP errors → `MarketDataError` with status code and response body
- Network errors → `MarketDataError` with description
- Parse errors → Individual bars skipped with warning log

---

## 4. DataProvider Orchestration

`DataProvider` is the high-level orchestrator:

### Request Flow

```
POST /market-data/fetch
  │
  ├── Validate product_key exists in contracts.yaml
  ├── Validate symbols against allowed contracts/spreads
  ├── Resolve spread legs (FFN26-FFQ26 → {FFN26, FFQ26})
  ├── Deduplicate legs across multiple spreads
  ├── Fetch all unique legs via QHAdapter
  ├── Cache each OHLCVSeries
  ├── Compute spread quotes for spread symbols
  ├── Cache spread quotes
  ├── Collect snapshots for outright symbols
  │
  ▼
MarketDataResponse
```

### Spread Construction

For each requested spread symbol (e.g., `FFN26-FFQ26`):

1. Split on `-` → front_leg = `FFN26`, back_leg = `FFQ26`
2. Retrieve cached OHLCV for both legs
3. Get latest close for each leg
4. Compute: `spread_bp = (front_close - back_close) × 100`
5. Create `SpreadQuote` model
6. Cache as spread quote

### Request Example

```json
POST /market-data/fetch
{
  "product_key": "fed_funds",
  "symbols": ["FFN26", "FFQ26", "FFN26-FFQ26"],
  "timeframe": "1H"
}
```

### Response Example

```json
{
  "success": true,
  "symbols_loaded": ["FFN26", "FFQ26", "FFN26-FFQ26"],
  "bars_per_symbol": {
    "FFN26": 500,
    "FFQ26": 500
  },
  "snapshots": [
    {
      "symbol": "FFN26",
      "last_price": 95.500,
      "volume": 12500.0,
      "high": 95.520,
      "low": 95.475,
      "change": 0.010,
      "change_pct": 0.01
    }
  ],
  "spread_quotes": [
    {
      "spread_symbol": "FFN26-FFQ26",
      "front_leg": "FFN26",
      "back_leg": "FFQ26",
      "front_price": 95.500,
      "back_price": 95.515,
      "spread_bp": -1.5,
      "product_key": "fed_funds"
    }
  ],
  "errors": []
}
```

---

## 5. Ingest Endpoint

The ingest endpoint extends fetch with indicator computation:

```json
POST /market-data/ingest
{
  "product_key": "fed_funds",
  "symbols": ["FFN26", "FFQ26"],
  "timeframe": "1H",
  "compute_indicators": true
}
```

When `compute_indicators` is true:
1. All symbols are fetched and cached normally
2. For each symbol, `IndicatorEngine.compute_all(series)` is called
3. Indicator errors are logged as warnings but don't fail the request
4. Errors are appended to the response `errors` list

---

## 6. Query Endpoints

### Snapshots

```
GET /market-data/snapshots
```

Returns all cached market snapshots and spread quotes:
```json
{
  "snapshots": {
    "FFN26": { "symbol": "FFN26", "last_price": 95.500, ... },
    "FFQ26": { "symbol": "FFQ26", "last_price": 95.515, ... }
  },
  "spreads": {
    "FFN26-FFQ26": { "spread_bp": -1.5, ... }
  }
}
```

### OHLCV Data

```
GET /market-data/ohlcv/FFN26/1H
```

Returns cached bars for charting:
```json
{
  "symbol": "FFN26",
  "timeframe": "1H",
  "bars": [
    {"timestamp": "2026-01-15T14:00:00", "open": 95.490, "high": 95.510, "low": 95.485, "close": 95.500, "volume": 250.0},
    ...
  ],
  "count": 500
}
```

### Indicators

```
GET /market-data/indicators/FFN26/1H
```

Returns the full `IndicatorSet` for the symbol/timeframe.

---

## 7. Error Responses

| Status | Condition | Detail |
|---|---|---|
| 404 | Contract not in config | "Contract 'XYZ' not in allowed contracts for fed_funds" |
| 404 | Spread not in config | "Spread 'XYZ-ABC' not in allowed spreads for fed_funds" |
| 404 | No cached data | "No data for FFN26:1H" |
| 502 | External API error | "HTTP 500 fetching FFN26: Internal Server Error" |
| 500 | Unexpected error | Error message string |
