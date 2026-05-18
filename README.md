# ZQ Strategy Planning Platform

## CME Fed Funds Futures (ZQ) — Institutional Strategy Planner

Production-grade strategy planning engine for CME Fed Funds Futures outrights and calendar spreads. This is a **planning-only** platform — no order submission, execution routing, or position management.

### Features

- **7 Institutional Strategies**: TrendFedRepricing, MeanReversionRange, EventMomentum, EventFade, VolatilityFade, CurveSteepener, CurveFlattener
- **Regime Classification**: Rule-based with manual override, event locks, and expiration
- **Indicator Engine**: ATR (Wilder), SMA, EMA, Donchian, Bollinger, DCW with caching
- **Risk Engine**: Sizing, ladders, commission/slippage modeling, R:R computation
- **Spread Analysis**: Calendar spreads in basis points with automated computation
- **Configuration-Driven**: YAML-based contracts and strategy settings
- **Bloomberg-Style UI**: Institutional frontend with TradingView charts

---

### Quick Start

#### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env         # Edit with your API credentials
uvicorn main:app --reload
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

#### Docker
```bash
docker-compose up --build
```

### API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| POST | /api/market-data/ingest | Ingest OHLCV bars |
| POST | /api/market-data/fetch | Fetch from external API |
| GET | /api/market-data/contracts | List contracts |
| GET | /api/market-data/snapshots | Get spread snapshots |
| POST | /api/strategy/evaluate | Evaluate all strategies |
| GET | /api/strategy/signal?product=X | Best signal |
| GET | /api/strategy/definitions | Strategy definitions |
| GET | /api/regime/current | Current regime |
| PUT | /api/regime/update | Override regime |
| GET | /api/account/config | Account config |
| PUT | /api/account/config | Update account |

### Tests
```bash
cd backend
pip install pytest pytest-asyncio pytest-cov
pytest tests/ -v
```

### Architecture

```
backend/
├── app/
│   ├── contracts/     # Pydantic v2 domain models
│   ├── services/      # Business logic engines
│   ├── strategies/    # Strategy definitions
│   ├── routes/        # Thin API handlers
│   ├── adapters/      # External API translation
│   ├── config/        # YAML configs + settings
│   ├── utils/         # Math, spread, datetime helpers
│   └── core/          # Logging, DI container
├── tests/
└── main.py

frontend/
├── src/
│   ├── charts/        # TradingView chart components
│   ├── components/    # UI components
│   ├── hooks/         # React Query hooks
│   ├── layouts/       # Sidebar, layouts
│   ├── pages/         # Dashboard page
│   ├── services/      # Axios API layer
│   ├── store/         # Zustand state
│   └── types/         # TypeScript types
```

### Market Conventions

- **Outrights**: Price format (96.500), tick=0.005, tick_value=$20.835
- **Spreads**: Basis points internally, spread_bp=(front-back)*100, tick=0.5bp
