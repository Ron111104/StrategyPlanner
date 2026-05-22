# ZQ Strategy Planner — Institutional CME Fed Funds Futures Strategy Planning Platform

> **Institutional-grade discretionary macro strategy planning workstation for CME Fed Funds Futures (ZQ) outrights and calendar spreads.**

**This platform is a strategy planning tool exclusively.** It does NOT execute trades, connect to brokers, or manage live positions. It is purpose-built for macro traders, quantitative researchers, and institutional trading desks that require disciplined, structured, and repeatable analysis workflows for short-term interest rate (STIR) products.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Goals and Design Philosophy](#goals-and-design-philosophy)
- [Architecture Summary](#architecture-summary)
- [Feature List](#feature-list)
- [Screenshots](#screenshots)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Docker Setup](#docker-setup)
- [Environment Variables](#environment-variables)
- [API Overview](#api-overview)
- [Strategy Overview](#strategy-overview)
- [Ladder Generation Overview](#ladder-generation-overview)
- [Indicator Engine Overview](#indicator-engine-overview)
- [Deployment Guide](#deployment-guide)
- [Testing Guide](#testing-guide)
- [Project Structure](#project-structure)
- [Documentation Index](#documentation-index)
- [Roadmap](#roadmap)
- [License](#license)

---

## Project Overview

The ZQ Strategy Planner is a self-contained, modular, async-first web application that provides:

1. **OHLCV Data Ingestion** — Fetch and normalize candlestick data from an external market data API (QH API) for any configured CME STIR contract or calendar spread.
2. **Indicator Engine** — Compute 30+ institutional-grade technical indicators across six categories: trend, volatility, momentum, structure, spread, and liquidity.
3. **Regime Classification** — Manual selection (with advisory suggestions) of market regime (trend, range, volatility, event) and macro bias (hawkish, dovish, neutral).
4. **Strategy Engine** — Evaluate seven named discretionary strategies against current market data, indicators, and regime to produce directional signals with confidence scores.
5. **Adaptive Ladder Engine** — Dynamically generate institutional entry ladders with computed spacing, lot distribution, stops, targets, and risk sizing — all derived from market data, ATR, DCW, regime, and strategy context.
6. **Multi-Timeframe Engine** — Score alignment across 1M, 5M, 15M, 1H, 4H, and 1D timeframes to confirm or adjust strategy confidence and ladder parameters.
7. **Risk Engine** — Convert prices to ticks, compute position sizing, slippage, commissions, total risk, and risk/reward ratios for both outrights and spreads.
8. **Frontend Dashboard** — Institutional-grade dark terminal UI built with Jinja2, Alpine.js, HTMX, TailwindCSS CDN, and TradingView Lightweight Charts CDN.

The platform supports both **outright contracts** (e.g., FFN26 at 95.500) and **calendar spreads** (e.g., FFN26-FFQ26 quoted in basis points).

---

## Goals and Design Philosophy

| Principle | Implementation |
|---|---|
| **Institutional rigor** | Every indicator uses correct mathematical formulas (Wilder smoothing for ATR/RSI, proper EMA seeding, annualized volatility) |
| **Configuration-driven** | All products, contracts, spreads, tick sizes, and strategy parameters live in YAML — zero hardcoding |
| **Separation of concerns** | Thin API routes delegate to service engines; contracts define typed data boundaries |
| **Async-first** | FastAPI + httpx.AsyncClient for non-blocking I/O throughout the data pipeline |
| **No frontend build tools** | All frontend libraries loaded from CDN — no npm, no node_modules, no webpack |
| **Fully typed** | Pydantic v2 models for all data boundaries; Python type hints everywhere |
| **Immediately runnable** | No placeholders, no pseudo-code — every module is production-ready |
| **Modular extensibility** | Adding a new product, strategy, or indicator requires only YAML config and a single Python class |

---

## Architecture Summary

```
                    +-------------------+
                    |   Browser / UI    |
                    | (Jinja2+Alpine+   |
                    |  HTMX+TW+LWC)    |
                    +--------+----------+
                             |
                    +--------v----------+
                    |    FastAPI App     |
                    |  (routes/pages)   |
                    +--------+----------+
                             |
          +------------------+------------------+
          |                  |                  |
  +-------v------+  +-------v------+  +-------v------+
  | Data Provider|  | Strategy Eng |  | Ladder Engine|
  | + QH Adapter |  | (7 strats)   |  | (adaptive)   |
  +--------------+  +--------------+  +--------------+
          |                  |                  |
  +-------v------+  +-------v------+  +-------v------+
  | Indicator Eng|  | Regime Engine|  |  MTF Engine  |
  | (30+ indics) |  | (4 regimes)  |  | (6 TFs)      |
  +--------------+  +--------------+  +--------------+
          |                  |                  |
          +------------------+------------------+
                             |
                    +--------v----------+
                    |   Cache Manager   |
                    |  (singleton RAM)  |
                    +--------+----------+
                             |
                    +--------v----------+
                    |  YAML Config      |
                    | contracts.yaml    |
                    | strategy_settings |
                    +-------------------+
```

**Full architecture documentation:** [`docs/architecture.md`](docs/architecture.md)

---

## Feature List

### Data Pipeline
- Async OHLCV fetching from external QH API with dynamic URL construction
- Multi-format timestamp parsing (ISO 8601, Unix seconds, Unix milliseconds)
- Automatic calendar spread construction from outright legs
- Spread quoting in basis points: `spread_bp = (front_price - back_price) * 100`
- In-memory caching with singleton CacheManager

### Indicators (30+)
- **Trend:** SMA, EMA, HMA (Hull), KAMA (Kaufman Adaptive), VWAP, Anchored VWAP
- **Volatility:** ATR (Wilder), NATR, Historical Vol, Realized Vol, Bollinger Width, DCW, Keltner Channels
- **Momentum:** RSI (Wilder), Stochastic RSI, MACD, ROC, Momentum, PPO
- **Structure:** Donchian Channels, Bollinger Bands, Range Compression, Expansion Detection, Session Range
- **Spread:** Z-score, Mean Deviation, Velocity, Acceleration, Curve Slope, Curve Momentum, Spread ATR, Spread DCW
- **Liquidity:** Relative Volume, Volume Delta

### Strategies (7)
- Trend Fed Repricing — trend-following for macro rate repricing
- Mean Reversion Range — Bollinger/SMA reversion in range markets
- Event Momentum — capture post-event momentum breakouts
- Event Fade — fade overextended event moves
- Volatility Fade — profit from volatility contraction
- Curve Steepener — spread strategy for steepening
- Curve Flattener — spread strategy for flattening

### Adaptive Ladder Engine
- Regime-dependent spacing (ATR for trend/volatility, DCW for range, single-entry for event)
- Four lot distribution profiles: pyramid, equal, front-loaded, back-loaded
- Timeframe-adjusted spacing multipliers (1M=0.3x through 1D=2.5x)
- Automatic direction inference from EMA alignment, Bollinger position, macro bias
- Dynamic stop, target_1, target_2 computation from ATR multiples
- Volatility percentile and MTF alignment scoring

### Multi-Timeframe Engine
- Trend alignment scoring across 1M through 1D
- Volatility alignment (ATR percentile rank)
- Structure alignment (compression/expansion)
- Composite weighted scoring for ladder adjustment
- Spacing, confidence, and position size adjustment factors

### Risk Engine
- Tick math for outrights and basis-point math for spreads
- Position sizing from account risk parameters
- Slippage and commission modeling
- Ladder-level risk aggregation
- Risk/reward ratio computation

---

## Screenshots

> Screenshots will be added after UI stabilization.

| View | Description |
|---|---|
| Dashboard | Main overview with regime badge, signals, spreads, chart |
| Strategy Planner | Strategy evaluation with signal cards and entry/exit plans |
| Ladder Planner | Adaptive ladder with levels, stops, targets, risk/reward |
| Risk Planner | Position sizing, tick math, risk assessment |
| Replay Engine | Historical bar-by-bar scenario analysis |

---

## Quick Start

```bash
# 1. Clone
git clone <repository-url>
cd StrategyPlanner

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Edit .env with your QH API credentials

# 5. Run
python run.py

# 6. Open browser
# http://localhost:8000
```

---

## Installation

### Prerequisites
- **Python 3.12+** (required for `type` union syntax)
- **pip** (no npm, no node, no frontend build tools)

### Dependencies (requirements.txt)
| Package | Version | Purpose |
|---|---|---|
| fastapi | 0.115.6 | Async web framework |
| uvicorn[standard] | 0.34.0 | ASGI server |
| pydantic | 2.10.3 | Data validation and typed models |
| pydantic-settings | 2.7.0 | Environment-based configuration |
| httpx | 0.28.1 | Async HTTP client for API fetching |
| numpy | 2.2.1 | Vectorized indicator computation |
| pandas | 2.2.3 | Data manipulation utilities |
| pyyaml | 6.0.2 | YAML configuration parsing |
| structlog | 24.4.0 | Structured JSON logging |
| jinja2 | 3.1.5 | Server-side HTML templating |
| python-dotenv | 1.0.1 | .env file loading |
| python-multipart | 0.0.20 | Form data parsing |
| aiofiles | 24.1.0 | Async file serving |
| orjson | 3.10.13 | Fast JSON serialization |
| pytest | 8.3.4 | Testing framework |
| pytest-asyncio | 0.25.0 | Async test support |
| pytest-cov | 6.0.0 | Coverage reporting |

---

## Docker Setup

```bash
# Build and run with docker-compose
docker-compose up --build -d

# View logs
docker-compose logs -f strategy-planner

# Stop
docker-compose down
```

The Docker configuration:
- Uses `python:3.12-slim` base image
- Installs dependencies in a cached layer
- Exposes port 8000
- Mounts `app/config/` as a read-only volume for hot config reloads
- Includes a healthcheck hitting `/health` every 30 seconds
- Restarts unless explicitly stopped

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | StrategyPlanner | Application display name |
| `APP_ENV` | development | Environment: development, staging, production |
| `APP_DEBUG` | true | Enable debug mode and hot reload |
| `APP_HOST` | 0.0.0.0 | Bind host |
| `APP_PORT` | 8000 | Bind port |
| `QH_API_BASE_URL` | https://api.example.com | External market data API base URL |
| `QH_API_KEY` | (empty) | Bearer token for API authentication |
| `QH_API_TIMEOUT` | 30 | HTTP request timeout in seconds |
| `LOG_LEVEL` | INFO | Logging level: DEBUG, INFO, WARNING, ERROR |
| `LOG_FORMAT` | json | Log format: json (structured) or console (human-readable) |
| `CACHE_TTL_SECONDS` | 300 | Cache time-to-live (future use) |
| `MAX_BARS_PER_REQUEST` | 5000 | Maximum OHLCV bars per API request |

---

## API Overview

All API routes are prefixed and return JSON. Full documentation: [`docs/api_reference.md`](docs/api_reference.md)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/market-data/fetch` | Fetch OHLCV from external API |
| POST | `/market-data/ingest` | Fetch + compute indicators |
| GET | `/market-data/snapshots` | Get cached snapshots and spreads |
| GET | `/market-data/ohlcv/{symbol}/{tf}` | Get cached OHLCV bars |
| GET | `/market-data/indicators/{symbol}/{tf}` | Get cached indicators |
| POST | `/strategy/evaluate` | Evaluate strategies |
| PUT | `/regime/update` | Set regime and macro bias |
| GET | `/regime/current` | Get current regime state |
| GET | `/regime/suggest` | Get regime advisory |
| POST | `/ladder/generate` | Generate adaptive strategy ladder |
| GET | `/ladder/strategies` | List available strategies |
| GET | `/ladder/mtf/{symbol}/{tf}` | Run multi-timeframe analysis |
| GET | `/account/config` | Get account configuration |
| PUT | `/account/config` | Update account configuration |

---

## Strategy Overview

Each strategy is a self-contained Python class inheriting from `BaseStrategy` with `evaluate()` and `build_entry_exit_plan()` methods. Strategies are enabled/disabled per regime and timeframe via `strategy_settings.yaml`.

| Strategy | Regime | Direction | Instruments |
|---|---|---|---|
| Trend Fed Repricing | trend | long/short | outrights |
| Mean Reversion Range | range | long/short | outrights |
| Event Momentum | event | long/short | outrights |
| Event Fade | event | long/short | outrights |
| Volatility Fade | volatility | long/short | outrights |
| Curve Steepener | trend, range | steepener | spreads only |
| Curve Flattener | trend, range | flattener | spreads only |

Full documentation: [`docs/strategies.md`](docs/strategies.md)

---

## Ladder Generation Overview

The Adaptive Ladder Engine is the core differentiator of this platform. Rather than requiring the trader to manually input ladder prices, the engine **dynamically computes** all entry levels, stops, targets, and sizing from:

- Current OHLCV price action
- ATR and DCW volatility measures
- Market regime (trend, range, volatility, event)
- Strategy-specific parameters
- Timeframe-adjusted spacing
- Lot distribution profiles
- Account risk limits

Full documentation: [`docs/ladder_engine.md`](docs/ladder_engine.md)

---

## Indicator Engine Overview

The indicator engine computes 30+ indicators organized into six categories. All indicators use correct mathematical formulas — Wilder smoothing for ATR/RSI, proper EMA seeding, annualized historical volatility, Hull Moving Average with WMA composition, Kaufman Adaptive Moving Average with efficiency ratio.

Spread-specific indicators (Z-score, velocity, acceleration, curve slope) are only computed for spread symbols (detected by `-` in symbol name).

Full documentation: [`docs/indicators.md`](docs/indicators.md)

---

## Deployment Guide

### Local Development
```bash
python run.py
# Runs uvicorn with --reload on 0.0.0.0:8000
```

### Production (Gunicorn + Uvicorn workers)
```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker
```bash
docker-compose up --build -d
```

Full documentation: [`docs/deployment.md`](docs/deployment.md)

---

## Testing Guide

```bash
# Run all tests
python -m pytest app/tests/ -v

# Run with coverage
python -m pytest app/tests/ --cov=app --cov-report=html

# Run specific test module
python -m pytest app/tests/test_ladder.py -v
python -m pytest app/tests/test_new_indicators.py -v
python -m pytest app/tests/test_mtf.py -v
```

**Current test count: 177 tests passing.**

| Test Module | Tests | Coverage Area |
|---|---|---|
| test_config.py | Config loading and validation |
| test_market_data.py | OHLCV models, cache, adapter parsing |
| test_spreads.py | Spread BP computation, conventions |
| test_signals.py | Signal models and strategy signals |
| test_strategies.py | All 7 strategy evaluate methods |
| test_new_indicators.py | 31 tests for all expanded indicators |
| test_ladder.py | 22 tests for ladder engine |
| test_mtf.py | 14 tests for MTF engine |
| test_edge_cases.py | Minimal bars, flat prices, zero volume |
| test_latency.py | Performance benchmarks |
| test_api.py | FastAPI endpoint integration tests |

Full documentation: [`docs/testing.md`](docs/testing.md)

---

## Project Structure

```
StrategyPlanner/
+-- app/
|   +-- adapters/
|   |   +-- __init__.py
|   |   +-- qh_adapter.py          # External API adapter
|   +-- config/
|   |   +-- contracts.yaml          # Product/contract definitions
|   |   +-- strategy_settings.yaml  # Indicator/strategy/ladder config
|   |   +-- loader.py               # YAML config loader with caching
|   +-- contracts/
|   |   +-- __init__.py             # Central model exports
|   |   +-- market_data.py          # OHLCVBar, OHLCVSeries, SpreadQuote
|   |   +-- products.py             # ProductConfig, TimeframeEnum
|   |   +-- signals.py              # Signal, StrategySignal, SignalCard
|   |   +-- strategy.py             # StrategyDefinition, EntryExitPlan
|   |   +-- indicators.py           # IndicatorResult, IndicatorSet
|   |   +-- ladder.py               # AdaptiveLadder, LadderRequest
|   |   +-- regime.py               # RegimeType, MacroBias, RegimeState
|   |   +-- risk.py                 # RiskProfile, LadderPlan, PositionSizing
|   |   +-- requests.py             # API request models
|   |   +-- responses.py            # API response models
|   +-- core/
|   |   +-- settings.py             # Pydantic Settings from .env
|   |   +-- logging.py              # structlog configuration
|   |   +-- exceptions.py           # Exception hierarchy
|   |   +-- dependencies.py         # FastAPI dependency injection
|   +-- routes/
|   |   +-- __init__.py             # Router registry
|   |   +-- health.py               # Health check
|   |   +-- market_data.py          # Data fetch/ingest/query
|   |   +-- strategy.py             # Strategy evaluation
|   |   +-- regime.py               # Regime management
|   |   +-- account.py              # Account configuration
|   |   +-- ladder.py               # Ladder generation + MTF
|   |   +-- pages.py                # Jinja2 page routes
|   +-- services/
|   |   +-- __init__.py             # Service exports
|   |   +-- cache.py                # Singleton CacheManager
|   |   +-- data_provider.py        # Data orchestration
|   |   +-- indicator_engine.py     # 30+ indicator computations
|   |   +-- regime_engine.py        # Regime management + advisory
|   |   +-- strategy_engine.py      # Multi-strategy orchestration
|   |   +-- ladder_engine.py        # Adaptive ladder generation
|   |   +-- mtf_engine.py           # Multi-timeframe analysis
|   |   +-- risk_engine.py          # Risk/sizing calculations
|   +-- strategies/
|   |   +-- __init__.py             # Strategy registry
|   |   +-- base.py                 # BaseStrategy abstract class
|   |   +-- trend_fed_repricing.py
|   |   +-- mean_reversion_range.py
|   |   +-- event_momentum.py
|   |   +-- event_fade.py
|   |   +-- volatility_fade.py
|   |   +-- curve_steepener.py
|   |   +-- curve_flattener.py
|   +-- static/
|   |   +-- js/                     # Frontend JavaScript
|   |   +-- css/                    # Custom styles
|   +-- templates/
|   |   +-- layouts/base.html       # Base layout with nav
|   |   +-- components/             # Reusable template components
|   |   +-- dashboard/index.html
|   |   +-- strategy/index.html
|   |   +-- risk/index.html
|   |   +-- ladder/index.html
|   |   +-- replay/index.html
|   +-- tests/
|   |   +-- conftest.py             # Shared fixtures
|   |   +-- test_*.py               # Test modules
|   +-- main.py                     # FastAPI app factory
+-- docs/                           # Full documentation suite
+-- .env.example                    # Environment template
+-- Dockerfile
+-- docker-compose.yml
+-- requirements.txt
+-- run.py                          # Entry point
+-- README.md
```

---

## Documentation Index

| Document | Description |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | System architecture, design decisions, diagrams |
| [`docs/system_flow.md`](docs/system_flow.md) | End-to-end data and decision flow |
| [`docs/configuration.md`](docs/configuration.md) | YAML config files, environment variables, extensibility |
| [`docs/contracts.md`](docs/contracts.md) | All Pydantic models, typing, validation |
| [`docs/indicators.md`](docs/indicators.md) | All 30+ indicators with formulas and usage |
| [`docs/strategies.md`](docs/strategies.md) | All 7 strategies with logic and conditions |
| [`docs/ladder_engine.md`](docs/ladder_engine.md) | Adaptive ladder generation deep-dive |
| [`docs/risk_engine.md`](docs/risk_engine.md) | Tick math, sizing, risk calculations |
| [`docs/regime_engine.md`](docs/regime_engine.md) | Regime types, macro bias, strategy gating |
| [`docs/market_data.md`](docs/market_data.md) | QH API integration, OHLCV, spreads |
| [`docs/api_reference.md`](docs/api_reference.md) | All REST endpoints with examples |
| [`docs/frontend.md`](docs/frontend.md) | Jinja2, Alpine.js, HTMX, chart rendering |
| [`docs/backend.md`](docs/backend.md) | FastAPI structure, services, async patterns |
| [`docs/caching.md`](docs/caching.md) | CacheManager, lifecycle, future Redis |
| [`docs/testing.md`](docs/testing.md) | Test suite, coverage, CI recommendations |
| [`docs/deployment.md`](docs/deployment.md) | Local, Docker, production deployment |
| [`docs/mtf_engine.md`](docs/mtf_engine.md) | Multi-timeframe alignment engine |
| [`docs/replay_engine.md`](docs/replay_engine.md) | Historical replay and scenario analysis |
| [`docs/troubleshooting.md`](docs/troubleshooting.md) | Common issues and resolutions |
| [`docs/future_extensions.md`](docs/future_extensions.md) | Roadmap and planned enhancements |

---

## Roadmap

### Phase 1 (Complete)
- [x] Core platform architecture
- [x] YAML configuration system
- [x] QH API adapter with async fetching
- [x] 30+ indicator engine
- [x] 7 named strategies
- [x] Regime engine with manual selection
- [x] Adaptive ladder engine
- [x] Multi-timeframe engine
- [x] Risk engine
- [x] Frontend dashboard with institutional UI
- [x] Docker deployment
- [x] 177 passing tests

### Phase 2 (Planned)
- [ ] N-leg spread structures (butterflies, condors)
- [ ] AI-assisted regime classification
- [ ] ML-based signal scoring
- [ ] Real-time WebSocket streaming
- [ ] Redis cache backend
- [ ] PostgreSQL persistence
- [ ] Portfolio-level optimization
- [ ] Enhanced replay engine with scenario branching

### Phase 3 (Future)
- [ ] Execution integration (read-only broker connections)
- [ ] Live P&L tracking
- [ ] Multi-desk collaboration
- [ ] Custom indicator SDK
- [ ] Strategy backtesting framework

---

## License

Internal use only. Proprietary institutional trading software.

---

*Built for institutional macro trading desks. Configuration-driven. Fully typed. Immediately runnable.*
