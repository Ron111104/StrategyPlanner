# Backend Documentation

> FastAPI application structure, routing, service layer, adapters, dependency injection, async architecture, exception handling, and structured logging.

---

## 1. Application Entry Point

**File:** `run.py`

```python
uvicorn.run(
    "app.main:app",
    host=settings.APP_HOST,     # 0.0.0.0
    port=settings.APP_PORT,     # 8000
    reload=settings.APP_DEBUG,  # True in development
    log_level=settings.LOG_LEVEL.lower(),
)
```

In development mode (`APP_DEBUG=true`), uvicorn runs with `--reload` (WatchFiles-based hot reload). In production, the `reload` flag is disabled.

---

## 2. FastAPI Application Factory

**File:** `app/main.py`

The application is created as a module-level `app` object:

```python
app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)
```

### Startup Sequence

1. `setup_logging()` — Configure structlog with JSON or console renderer
2. Mount static files at `/static`
3. Configure Jinja2 template directory
4. Register CORS middleware
5. Include all routers:
   - `health_router` — `/health`
   - `market_data_router` — `/market-data`
   - `strategy_router` — `/strategy`
   - `regime_router` — `/regime`
   - `account_router` — `/account`
   - `ladder_router` — `/ladder`
   - `pages_router` — `/` (HTML pages)
6. Log startup event

### Lifespan Events

```python
@app.on_event("startup")
async def on_startup():
    logger.info("application_starting", app=settings.APP_NAME, env=settings.APP_ENV)

@app.on_event("shutdown")
async def on_shutdown():
    logger.info("application_shutting_down")
```

---

## 3. Routing Architecture

### Router Registry

**File:** `app/routes/__init__.py`

All routers are exported from a single registry:

```python
from app.routes.health import router as health_router
from app.routes.market_data import router as market_data_router
from app.routes.strategy import router as strategy_router
from app.routes.regime import router as regime_router
from app.routes.account import router as account_router
from app.routes.ladder import router as ladder_router
from app.routes.pages import router as pages_router
```

### Route Prefixes

| Router | Prefix | Tags |
|---|---|---|
| health | `/health` | health |
| market_data | `/market-data` | market-data |
| strategy | `/strategy` | strategy |
| regime | `/regime` | regime |
| account | `/account` | account |
| ladder | `/ladder` | ladder |
| pages | (none) | pages |

### Thin Route Pattern

Routes follow a strict pattern: **validate → delegate → return**. No business logic in route handlers.

```python
@router.post("/generate", response_model=LadderResponse)
async def generate_ladder(request: LadderRequest) -> LadderResponse:
    try:
        engine = LadderEngine()
        ladder = engine.generate(request)
        return LadderResponse(success=True, ladder=ladder)
    except InsufficientDataError as e:
        return LadderResponse(success=False, error=str(e))
    except Exception as e:
        logger.error("ladder_error", error=str(e))
        return LadderResponse(success=False, error=str(e))
```

---

## 4. Service Layer

### Design Principles

- Services are **stateless classes** instantiated per request
- State is stored in `CacheManager` (singleton)
- Services read configuration via `ConfigLoader` functions
- Services do not call other services' public APIs directly (with documented exceptions)

### Service Registry

**File:** `app/services/__init__.py`

```python
from app.services.cache import CacheManager
from app.services.data_provider import DataProvider
from app.services.indicator_engine import IndicatorEngine
from app.services.regime_engine import RegimeEngine
from app.services.strategy_engine import StrategyEngine
from app.services.risk_engine import RiskEngine
from app.services.ladder_engine import LadderEngine
from app.services.mtf_engine import MTFEngine
```

### Service Instantiation

Services are created in route handlers, not injected via FastAPI DI:

```python
@router.post("/generate")
async def generate_ladder(request: LadderRequest):
    engine = LadderEngine()   # Created per request
    return engine.generate(request)
```

This keeps services simple and avoids complex DI graphs. The `CacheManager` singleton inside each service ensures shared state.

---

## 5. Adapter Layer

### QHAdapter

**File:** `app/adapters/qh_adapter.py`

The adapter pattern isolates external API communication:

```python
class QHAdapter:
    def __init__(self, client: Optional[httpx.AsyncClient] = None)
    async def fetch_ohlcv(self, symbol, timeframe, product_key, limit) -> OHLCVSeries
    async def fetch_multiple(self, symbols, timeframe, product_key) -> dict[str, OHLCVSeries]
```

**Key behaviors:**
- Accepts an optional `httpx.AsyncClient` (for dependency injection in tests)
- Creates its own client if none provided (and closes it after use)
- Maps internal timeframe codes to API-expected formats
- Handles multiple timestamp and field name formats
- Wraps all HTTP errors in `MarketDataError`

---

## 6. Dependency Injection

**File:** `app/core/dependencies.py`

FastAPI's DI system provides:

### HTTP Client

```python
async def get_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(settings.QH_API_TIMEOUT),
        headers={"Accept": "application/json"},
    ) as client:
        yield client
```

Used in routes:
```python
@router.post("/fetch")
async def fetch_market_data(
    request: FetchMarketDataRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
):
    provider = DataProvider(client=client)
    return await provider.fetch_market_data(...)
```

### Settings

```python
def get_app_settings() -> Settings:
    return get_settings()
```

---

## 7. Async Architecture

### Async Boundaries

| Layer | Async? | Reason |
|---|---|---|
| Route handlers | Yes | FastAPI async request handling |
| DataProvider | Yes | Calls QHAdapter which uses httpx |
| QHAdapter | Yes | httpx.AsyncClient for HTTP calls |
| IndicatorEngine | No | CPU-bound NumPy computation |
| LadderEngine | No | CPU-bound computation |
| MTFEngine | No | CPU-bound computation |
| CacheManager | No | In-memory dict operations |

### Event Loop Safety

Synchronous computation (indicators, ladders) runs on the main event loop thread. For the current single-process deployment, this is acceptable. If computation latency becomes an issue, these can be offloaded to `asyncio.to_thread()` or a process pool.

---

## 8. Exception Handling

### Exception Hierarchy

**File:** `app/core/exceptions.py`

```
StrategyPlannerError (base)
├── ConfigurationError        — Invalid or missing configuration
├── ContractNotFoundError     — Unknown contract/spread symbol
├── ProductNotFoundError      — Unknown product key
├── MarketDataError           — External API fetch failure
├── InsufficientDataError     — Not enough bars for computation
├── IndicatorError            — Indicator computation failure
├── StrategyError             — Strategy evaluation failure
├── RiskError                 — Risk calculation failure
└── AdapterError              — External adapter call failure
```

### Exception → HTTP Status Mapping

| Exception | HTTP Status | Context |
|---|---|---|
| `ContractNotFoundError` | 404 | Symbol not in config |
| `ProductNotFoundError` | 404 | Product key not in config |
| `MarketDataError` | 502 | External API failure |
| `InsufficientDataError` | 422 | Not enough bars |
| `ConfigurationError` | 500 | Missing/invalid config |
| `StrategyError` | 500 | Strategy evaluation failure |
| All others | 500 | Unexpected errors |

---

## 9. Structured Logging

**File:** `app/core/logging.py`

The platform uses `structlog` for structured JSON logging:

### Configuration

```python
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
)
```

### Log Format

**JSON mode** (production):
```json
{
  "event": "ohlcv_fetched",
  "logger": "app.adapters.qh_adapter",
  "level": "info",
  "timestamp": "2026-01-15T14:30:00.000000Z",
  "symbol": "FFN26",
  "bars_count": 500
}
```

**Console mode** (development):
```
2026-01-15 14:30:00 [info     ] ohlcv_fetched    bars_count=500 symbol=FFN26
```

### Usage Pattern

```python
from app.core.logging import get_logger
logger = get_logger(__name__)

logger.info("ohlcv_fetched", symbol=symbol, bars_count=len(bars))
logger.warning("indicator_error", symbol=sym, error=str(e))
logger.error("fetch_error", error=str(e))
```

All log events include contextual key-value pairs as keyword arguments.

---

## 10. CORS Configuration

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

For production deployments, `allow_origins` should be restricted to the specific frontend domain.
