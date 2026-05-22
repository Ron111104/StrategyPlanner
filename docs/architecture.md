# Architecture Documentation

> System architecture, design decisions, modular structure, and data flow for the ZQ Strategy Planning Platform.

---

## 1. Design Philosophy

This platform is designed as an **institutional-grade discretionary macro strategy planning workstation**. It is NOT an execution system, auto-trader, or OMS. Every architectural decision serves the following principles:

- **Configuration over code** — Products, contracts, tick sizes, spreads, indicator parameters, strategy enablement, ladder settings, and risk parameters are all defined in YAML configuration files. Adding a new CME product requires zero code changes.
- **Separation of concerns** — API routes are thin dispatchers. Business logic lives exclusively in service engines. Data boundaries are enforced by Pydantic v2 models.
- **Async-first** — All external I/O (market data fetching) uses `httpx.AsyncClient` via FastAPI's async request handlers. Internal computation is synchronous NumPy for performance.
- **Single-process simplicity** — The platform runs as a single uvicorn process with in-memory caching. No external databases, message queues, or distributed state are required for the base deployment.
- **Institutional correctness** — Every indicator uses its canonical mathematical formula. ATR uses Wilder smoothing. RSI uses Wilder smoothing. EMA is seeded with the SMA of the first N bars. Historical volatility is annualized with √252. Spread basis points follow CME convention.

---

## 2. Why FastAPI

FastAPI was chosen over Flask, Django, and other frameworks for the following reasons:

| Requirement | FastAPI Advantage |
|---|---|
| Async HTTP client integration | Native `async/await` support — httpx.AsyncClient works natively |
| Automatic API documentation | Built-in Swagger UI at `/docs` and ReDoc at `/redoc` |
| Pydantic v2 integration | Request/response validation is automatic via type annotations |
| Performance | Starlette-based ASGI server with uvicorn — faster than WSGI |
| Type safety | Full type annotation support with IDE autocompletion |
| Dependency injection | Built-in DI system for HTTP clients and settings |
| WebSocket readiness | Native WebSocket support for future real-time streaming |

---

## 3. Why Jinja2 Instead of React

The frontend uses server-rendered Jinja2 templates enhanced with Alpine.js, HTMX, and TailwindCSS CDN. This was a deliberate architectural choice:

| Concern | Jinja2 + Alpine.js | React SPA |
|---|---|---|
| Build tooling | None — CDN only | Requires npm, webpack/vite, node_modules |
| Deployment complexity | Single Python process | Separate frontend build + static hosting |
| Server-side data | Direct template context injection | Requires API calls from client |
| Real-time updates | HTMX partial replacements | Full virtual DOM diffing |
| Bundle size | ~15KB (Alpine) + CDN | 200KB+ minimum (React + ReactDOM) |
| Institutional preference | Trading desks prefer minimal frontend complexity | Overkill for planning tool |

The constraint is explicit: **no npm, no node_modules, no frontend build tools**.

---

## 4. Why YAML Configuration

YAML was chosen over JSON, TOML, and database-stored config for:

- **Readability** — YAML is the most human-readable structured format for nested configuration
- **Comments** — YAML supports inline comments; JSON does not
- **Git-friendly** — Config changes are tracked in version control with meaningful diffs
- **Hot reload** — Config files are loaded with `@lru_cache` and can be reloaded at runtime via `reload_contracts_config()` and `reload_strategy_settings()`
- **Docker mount** — `docker-compose.yml` mounts `app/config/` as a read-only volume, allowing config updates without rebuilding the container

---

## 5. Backend Architecture

### Layer Diagram

```
┌─────────────────────────────────────────────────────────┐
│                      API Layer                          │
│  routes/health.py  routes/market_data.py                │
│  routes/strategy.py  routes/regime.py                   │
│  routes/account.py  routes/ladder.py  routes/pages.py   │
├─────────────────────────────────────────────────────────┤
│                    Service Layer                        │
│  DataProvider  IndicatorEngine  StrategyEngine          │
│  RegimeEngine  LadderEngine  MTFEngine  RiskEngine      │
├─────────────────────────────────────────────────────────┤
│                   Adapter Layer                         │
│  QHAdapter (httpx.AsyncClient → external API)           │
├─────────────────────────────────────────────────────────┤
│                   Contract Layer                        │
│  Pydantic v2 models: OHLCVBar, IndicatorResult,         │
│  StrategySignal, AdaptiveLadder, RiskProfile, etc.      │
├─────────────────────────────────────────────────────────┤
│                    Cache Layer                          │
│  CacheManager (singleton, in-memory dicts)              │
├─────────────────────────────────────────────────────────┤
│                   Config Layer                          │
│  contracts.yaml  strategy_settings.yaml  .env           │
│  loader.py (lru_cache)  settings.py (pydantic-settings) │
└─────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

**API Layer (routes/)** — Thin HTTP handlers. Accept request, validate via Pydantic, delegate to service, return response. No business logic. Routes are registered in `app/main.py` via `include_router()`.

**Service Layer (services/)** — All business logic. Each engine is a stateless class that reads from CacheManager and config. Engines do not call each other's public methods directly (with the exception of LadderEngine calling IndicatorEngine for on-demand computation).

**Adapter Layer (adapters/)** — External system integration. Currently only `QHAdapter` for OHLCV fetching. Adapters handle HTTP communication, response parsing, error mapping, and timestamp normalization.

**Contract Layer (contracts/)** — Pydantic v2 `BaseModel` classes that define all data boundaries. Every piece of data flowing between layers is a typed model. No raw dicts cross layer boundaries (except YAML config which is loaded as `dict[str, Any]`).

**Cache Layer (services/cache.py)** — Singleton `CacheManager` providing in-memory storage for OHLCV series, computed indicators, market snapshots, spread quotes, regime state, account configuration, and signal cards.

**Config Layer (config/)** — YAML files parsed at startup with `@lru_cache`. Environment variables loaded via `pydantic-settings` into `Settings` class.

---

## 6. Frontend Architecture

```
┌──────────────────────────────────────────┐
│              Browser                     │
├──────────────────────────────────────────┤
│  Jinja2 Templates (server-rendered HTML) │
│  ├── layouts/base.html (nav, sidebar)    │
│  ├── dashboard/index.html                │
│  ├── strategy/index.html                 │
│  ├── ladder/index.html                   │
│  ├── risk/index.html                     │
│  └── replay/index.html                   │
├──────────────────────────────────────────┤
│  Alpine.js (reactive state management)   │
│  - x-data, x-model, x-show, x-for       │
│  - Component-scoped state per page       │
├──────────────────────────────────────────┤
│  HTMX (partial page updates)            │
│  - hx-get, hx-post, hx-target           │
│  - Server-driven UI updates              │
├──────────────────────────────────────────┤
│  TailwindCSS CDN (utility-first CSS)    │
│  - Dark terminal theme                   │
│  - Responsive grid layouts               │
├──────────────────────────────────────────┤
│  TradingView Lightweight Charts CDN     │
│  - Candlestick rendering                │
│  - Indicator overlay support             │
├──────────────────────────────────────────┤
│  Custom JS (static/js/)                 │
│  - api.js — HTTP client helpers          │
│  - chart.js — Chart initialization       │
│  - ladder.js — Ladder page logic         │
└──────────────────────────────────────────┘
```

All frontend libraries are loaded from CDN in `layouts/base.html`:
- Alpine.js: `cdn.jsdelivr.net/npm/alpinejs`
- TailwindCSS: `cdn.tailwindcss.com`
- TradingView Lightweight Charts: `unpkg.com/lightweight-charts`
- HTMX: `unpkg.com/htmx.org`

---

## 7. Request Flow Diagram

### Market Data Fetch Flow

```
Browser                    FastAPI              DataProvider         QHAdapter          Cache
  │                          │                      │                   │                │
  │ POST /market-data/fetch  │                      │                   │                │
  │─────────────────────────>│                      │                   │                │
  │                          │ validate request      │                   │                │
  │                          │ FetchMarketDataRequest│                   │                │
  │                          │─────────────────────>│                   │                │
  │                          │                      │ resolve legs       │                │
  │                          │                      │ (outrights+spread) │                │
  │                          │                      │──────────────────>│                │
  │                          │                      │                   │ GET /api/ohlc/  │
  │                          │                      │                   │ (per symbol)    │
  │                          │                      │<──────────────────│                │
  │                          │                      │ parse bars         │                │
  │                          │                      │ compute spread BP  │                │
  │                          │                      │──────────────────────────────────>│
  │                          │                      │                                   │ set_ohlcv()
  │                          │                      │                                   │ set_spread()
  │                          │<─────────────────────│                   │                │
  │                          │ MarketDataResponse   │                   │                │
  │<─────────────────────────│                      │                   │                │
```

### Ladder Generation Flow

```
Browser                    FastAPI           LadderEngine       IndicatorEngine      Cache
  │                          │                   │                    │                │
  │ POST /ladder/generate    │                   │                    │                │
  │─────────────────────────>│                   │                    │                │
  │                          │ LadderRequest     │                    │                │
  │                          │──────────────────>│                    │                │
  │                          │                   │ get product config  │                │
  │                          │                   │ get OHLCV from cache│                │
  │                          │                   │────────────────────────────────────>│
  │                          │                   │ get indicators      │                │
  │                          │                   │────────────────────>│                │
  │                          │                   │                    │ compute_all()   │
  │                          │                   │<───────────────────│                │
  │                          │                   │ get regime          │                │
  │                          │                   │────────────────────────────────────>│
  │                          │                   │ infer direction     │                │
  │                          │                   │ compute spacing     │                │
  │                          │                   │ build levels        │                │
  │                          │                   │ compute stop/target │                │
  │                          │                   │ compute R:R         │                │
  │                          │ AdaptiveLadder    │                    │                │
  │                          │<──────────────────│                    │                │
  │<─────────────────────────│                   │                    │                │
```

---

## 8. Service Dependency Graph

```
DataProvider
  └── QHAdapter
  └── CacheManager

IndicatorEngine
  └── CacheManager
  └── ConfigLoader (strategy_settings.yaml)

StrategyEngine
  └── IndicatorEngine
  └── RegimeEngine
  └── CacheManager
  └── ConfigLoader

LadderEngine
  └── IndicatorEngine
  └── CacheManager
  └── ConfigLoader (contracts.yaml + strategy_settings.yaml)

MTFEngine
  └── IndicatorEngine
  └── CacheManager

RiskEngine
  └── ConfigLoader (contracts.yaml)
  └── CacheManager

RegimeEngine
  └── CacheManager
```

---

## 9. Module Interaction Rules

1. **Routes never contain business logic** — They validate, delegate, and return.
2. **Services read from CacheManager** — They never make HTTP calls directly (that is the adapter's job).
3. **Contracts are immutable data boundaries** — Once created, a Pydantic model instance is not mutated.
4. **Config is loaded once and cached** — `@lru_cache` on `load_contracts_config()` and `load_strategy_settings()` ensures YAML is parsed exactly once.
5. **Exceptions flow upward** — Service-level exceptions (`InsufficientDataError`, `ConfigurationError`) are caught and mapped to HTTP status codes in route handlers.
6. **Logging is structured** — Every log entry is a JSON object with `event`, `logger`, `level`, `timestamp`, and contextual fields.

---

## 10. Institutional Design Principles

### Why Regime-Gated Strategies

Institutional trading desks operate in regime-aware frameworks. A trend-following strategy should not fire signals during a range-bound market. The regime engine gates which strategies are evaluated, preventing signal noise.

### Why Adaptive Ladders

Professional traders do not enter at a single price. They ladder into positions across multiple levels to improve average entry and manage adverse selection. The ladder engine automates this process based on volatility (ATR, DCW), regime, and timeframe context.

### Why Multi-Timeframe Confirmation

A signal on the 1H chart that contradicts the 4H and 1D trend has lower conviction. The MTF engine scores alignment across all timeframes and adjusts ladder confidence, spacing, and size accordingly.

### Why Spread Basis Points

Calendar spreads on STIR products are quoted in basis points, not price. This platform maintains dual-unit support throughout: outrights in price, spreads in BP. The tick size for spreads is 0.5 bp (Fed Funds) or 0.25 bp (SOFR), with the same dollar tick value.

---

## 11. Security Model

- **API keys are stored in `.env`** and loaded via `pydantic-settings` — never hardcoded.
- **CORS is configured** but defaults to `allow_origins=["*"]` for development. Production deployments should restrict this.
- **No authentication** is built into the platform itself — it is assumed to run behind a corporate firewall or VPN. Future versions may add API key authentication.
- **Docker volumes are read-only** for config to prevent container-side modification.
