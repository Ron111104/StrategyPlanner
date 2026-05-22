# Caching Documentation

> In-memory cache architecture, lifecycle, data stored, invalidation, and future Redis migration.

---

## 1. Overview

The platform uses a **singleton in-memory cache** (`CacheManager`) for all runtime state. There is no external database or Redis instance in the base deployment. All data is ephemeral and lost on process restart.

**File:** `app/services/cache.py`

---

## 2. CacheManager Architecture

### Singleton Pattern

`CacheManager` uses the singleton pattern — all service instances share the same cache state:

```python
class CacheManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_stores()
        return cls._instance
```

### Internal Stores

| Store | Type | Key Format | Value Type |
|---|---|---|---|
| `_ohlcv` | `dict` | `"{symbol}:{timeframe}"` | `OHLCVSeries` |
| `_indicators` | `dict` | `"{symbol}:{timeframe}"` | `IndicatorSet` |
| `_snapshots` | `dict` | `"{symbol}"` | `MarketSnapshot` |
| `_spreads` | `dict` | `"{spread_symbol}"` | `SpreadQuote` |
| `_regime` | `RegimeState` | (single value) | `RegimeState` |
| `_account` | `dict` | (single value) | Account configuration dict |
| `_signals` | `dict` | `"{symbol}"` | `list[StrategySignal]` |

---

## 3. Cache Operations

### OHLCV Data

```python
# Store
cache.set_ohlcv(symbol, timeframe, series: OHLCVSeries) -> None

# Retrieve
cache.get_ohlcv(symbol, timeframe) -> Optional[OHLCVSeries]
```

OHLCV data is stored per symbol-timeframe pair. Fetching new data for the same pair overwrites the previous data completely (no merging or appending).

### Indicators

```python
# Store
cache.set_indicators(symbol, timeframe, indicators: IndicatorSet) -> None

# Retrieve
cache.get_indicators(symbol, timeframe) -> Optional[IndicatorSet]
```

Indicators are invalidated whenever new OHLCV data is fetched for the same symbol-timeframe.

### Market Snapshots

```python
# Store
cache.set_snapshot(symbol, snapshot: MarketSnapshot) -> None

# Retrieve
cache.get_snapshot(symbol) -> Optional[MarketSnapshot]
cache.get_all_snapshots() -> dict[str, MarketSnapshot]
```

### Spread Quotes

```python
# Store
cache.set_spread(spread_symbol, quote: SpreadQuote) -> None

# Retrieve
cache.get_spread(spread_symbol) -> Optional[SpreadQuote]
cache.get_all_spreads() -> dict[str, SpreadQuote]
```

### Regime State

```python
# Store
cache.set_regime(regime: RegimeState) -> None

# Retrieve
cache.get_regime() -> RegimeState  # Returns default if not set
```

Default regime: `RegimeType.RANGE`, `MacroBias.NEUTRAL`

### Account Configuration

```python
# Store
cache.set_account(config: dict) -> None

# Retrieve
cache.get_account() -> dict  # Returns defaults if not set
```

### Signal Cards

```python
# Store
cache.set_signals(symbol, signals: list[StrategySignal]) -> None

# Retrieve
cache.get_signals(symbol) -> list[StrategySignal]
cache.get_all_signals() -> dict[str, list[StrategySignal]]
```

---

## 4. Cache Lifecycle

### Population

1. **On data fetch** (`POST /market-data/fetch`):
   - OHLCV series cached per symbol-timeframe
   - Market snapshots cached per symbol
   - Spread quotes cached per spread symbol

2. **On data ingest** (`POST /market-data/ingest`):
   - Everything from fetch, plus:
   - Indicator sets cached per symbol-timeframe

3. **On regime update** (`PUT /regime/update`):
   - Regime state updated

4. **On strategy evaluation** (`POST /strategy/evaluate`):
   - Signal cards cached per symbol

5. **On account update** (`PUT /account/config`):
   - Account configuration updated

### Invalidation

Currently, cache invalidation is **explicit overwrite only**:
- New fetch for `FFN26:1H` overwrites previous `FFN26:1H` data
- No time-based expiration (TTL is configured but not enforced)
- No cross-key invalidation (changing OHLCV doesn't auto-invalidate indicators)

### Clear

```python
cache.clear() -> None  # Resets all stores to empty
```

This is used in tests (`conftest.py` has an autouse fixture that clears cache between tests).

---

## 5. Memory Considerations

### Typical Memory Usage

| Data Type | Per Entry | Typical Count | Total |
|---|---|---|---|
| OHLCVSeries (500 bars) | ~50 KB | 20 symbol-TF pairs | ~1 MB |
| IndicatorSet (30+ indicators) | ~200 KB | 20 symbol-TF pairs | ~4 MB |
| Snapshots | ~1 KB | 20 symbols | ~20 KB |
| Spread quotes | ~500 B | 10 spreads | ~5 KB |
| Signals | ~5 KB | 20 symbols | ~100 KB |

**Total estimated memory:** ~5 MB for a typical session. This is well within the limits of a single-process deployment.

### Scaling Concerns

If the platform grows to support:
- 100+ symbols × 6 timeframes = 600 OHLCV entries
- Each with 5000 bars instead of 500
- Full indicator sets

Memory usage could reach 100+ MB. At this point, Redis migration becomes necessary.

---

## 6. Thread Safety

The current singleton cache uses standard Python dicts, which are **not thread-safe** for concurrent writes. This is acceptable because:

- uvicorn runs a single event loop in a single thread
- All coroutine task switching happens at `await` points
- Cache reads/writes are synchronous dict operations (atomic at the GIL level)

For multi-worker deployments (gunicorn with multiple workers), each worker would have its own cache instance. This is acceptable for a planning tool but would require Redis for shared state.

---

## 7. Future: Redis Migration

### Planned Architecture

```
┌─────────────┐    ┌─────────────┐
│  Worker 1   │    │  Worker 2   │
│ CacheClient ├───>│ CacheClient │
└──────┬──────┘    └──────┬──────┘
       │                  │
       └────────┬─────────┘
                │
         ┌──────▼──────┐
         │    Redis     │
         │  (6379)      │
         └─────────────┘
```

### Migration Plan

1. **Add `redis-py` async client** to dependencies
2. **Create `RedisCacheManager`** implementing the same interface as `CacheManager`
3. **Serialize models** to JSON via Pydantic's `.model_dump_json()`
4. **TTL enforcement** — Each key type gets a configured TTL:
   - OHLCV: 5 minutes
   - Indicators: 5 minutes (computed from OHLCV)
   - Snapshots: 30 seconds
   - Regime: no TTL (persistent)
   - Signals: 5 minutes
5. **Docker Compose** — Add Redis service
6. **Feature flag** — `CACHE_BACKEND=memory|redis` in `.env`

### Interface Contract

The migration will be transparent to services because the cache interface remains identical:

```python
class CacheInterface(Protocol):
    def set_ohlcv(self, symbol: str, tf: str, series: OHLCVSeries) -> None: ...
    def get_ohlcv(self, symbol: str, tf: str) -> Optional[OHLCVSeries]: ...
    # ... same for all other methods
```
