# ZQ Strategy Planner

**CME Fed Funds Futures (ZQ) Institutional-Grade Strategy Planning Platform**

> ⚠️ This is a **strategy planning platform**, NOT an execution engine, OMS, auto-trading platform, or broker routing system.

## Purpose

Discretionary trade planning and analysis for CME Fed Funds Futures:

- **Strategy Evaluation** — 7 institutional strategies with regime-aware signal generation
- **Spread Analysis** — Calendar spread analysis in basis points
- **Regime Classification** — Event, Volatility, Trend, Range detection with priority hierarchy
- **Risk Management** — Position sizing, ladder planning, risk profiling
- **Scenario Planning** — Multi-scenario P&L with probability-weighted expected value
- **Replay Engine** — Historical bar-by-bar playback with signal evaluation
- **Curve Analysis** — Implied rate curve and spread heatmaps

## Supported Instruments

| Type | Contracts |
|------|-----------|
| **Outrights** | FFN25 through FFQ26 (14 contracts) |
| **Calendar Spreads** | FFN25-FFQ25, FFQ25-FFU25, ..., FFN26-FFQ26 (7 spreads) |

## Architecture

```
backend/
├── app/
│   ├── config/           # YAML configs, Settings, ContractLoader
│   ├── contracts/        # Pydantic v2 typed models (zero logic)
│   ├── core/             # DI container, logging, exceptions
│   ├── adapters/         # External API adapters (QHAdapter)
│   ├── services/         # Business logic engines
│   │   ├── indicator_engine.py    # ATR, SMA, EMA, Donchian, Bollinger, DCW
│   │   ├── regime_engine.py       # Regime classification
│   │   ├── risk_engine.py         # Position sizing, ladders, risk profiles
│   │   ├── strategy_engine.py     # Strategy orchestration
│   │   └── data_provider.py       # Data caching & ingestion
│   ├── strategies/       # 7 strategy definitions
│   ├── routes/           # FastAPI route handlers
│   ├── templates/        # Jinja2 HTML templates
│   ├── static/           # CSS, JS modules
│   ├── utils/            # Pure math/spread/datetime/validation helpers
│   └── tests/            # Pytest suite with benchmarks
```

## 7 Strategies

| # | Strategy | Regimes | Products |
|---|----------|---------|----------|
| 1 | Trend — Fed Repricing | Trend | Outrights |
| 2 | Mean Reversion — Range | Range | Outrights |
| 3 | Event Momentum | Event | Outrights |
| 4 | Event Fade | Event | Outrights |
| 5 | Volatility Fade | Volatility | Outrights |
| 6 | Curve Steepener | Trend, Range | Spreads |
| 7 | Curve Flattener | Trend, Range | Spreads |

## Quick Start

### 1. Install Dependencies

```bash
cd backend
python -m venv venv
venv\Scripts\activate     # Windows
# source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
copy .env.example .env
# Edit .env with your API keys
```

### 3. Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Access

- **Dashboard**: http://localhost:8000/
- **Strategy Evaluator**: http://localhost:8000/strategy
- **Spread Analysis**: http://localhost:8000/strategy/spread
- **Regime View**: http://localhost:8000/strategy/regime
- **Ladder Planner**: http://localhost:8000/risk
- **Position Sizing**: http://localhost:8000/risk/sizing
- **Scenario Planning**: http://localhost:8000/risk/scenarios
- **Replay Engine**: http://localhost:8000/replay
- **API Docs**: http://localhost:8000/docs

### 5. Run Tests

```bash
pytest
```

## Docker

```bash
docker-compose up --build
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | System health check |
| GET | `/api/market/bars/{product}` | Fetch OHLCV bars |
| GET | `/api/market/snapshot/{product}` | Market snapshot |
| POST | `/api/strategy/evaluate` | Evaluate strategies |
| GET | `/api/strategy/list` | List available strategies |
| GET | `/api/regime/{product}` | Get current regime |
| PUT | `/api/regime/{product}` | Update regime (manual override) |
| GET | `/api/account/config` | Get account configuration |
| PUT | `/api/account/config` | Update account configuration |
| POST | `/api/account/sizing` | Compute position size |
| POST | `/api/account/ladder` | Generate ladder plan |

## Tech Stack

- **Backend**: Python 3.12, FastAPI, Pydantic v2
- **Frontend**: Jinja2, Alpine.js, HTMX, TradingView Lightweight Charts
- **Data**: httpx async, in-memory caching
- **Testing**: pytest, pytest-asyncio
- **Deployment**: Docker, uvicorn
