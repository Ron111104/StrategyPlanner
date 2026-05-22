# Future Extensions & Roadmap

> Planned enhancements, architectural evolution, and advanced features for future phases.

---

## 1. Phase 2 — Near-Term Enhancements

### 1.1 N-Leg Spread Structures

**Current:** Only 2-leg calendar spreads (front-back) are supported.

**Planned:** Support for:
- **Butterflies** (3-leg): Buy 1 near, sell 2 middle, buy 1 far
- **Condors** (4-leg): Buy 1 near, sell 1 near-mid, sell 1 far-mid, buy 1 far
- **Packs** (4-leg): Simultaneous entry across 4 quarterly contracts
- **Bundles** (8-leg): Simultaneous entry across 8 contracts spanning 2 years

**Implementation:**
- Extend `contracts.yaml` with `structures` section defining leg configurations
- Create `SpreadStructure` Pydantic model with leg definitions and quoting conventions
- Extend `DataProvider` to construct multi-leg spread OHLCV
- Extend risk engine for multi-leg DV01 and convexity calculations

### 1.2 AI-Assisted Regime Classification

**Current:** Manual regime selection with advisory suggestions.

**Planned:** Automatic regime classification using:
- **Hidden Markov Model (HMM)** for regime state transitions
- **Random Forest classifier** trained on: ATR percentile, DCW ratio, Bollinger Width, RSI, volume profile, time-of-day
- **Ensemble voting** across multiple classifiers
- **Confidence distribution** (e.g., 70% trend, 20% range, 10% volatility)
- **Override capability** — trader always has final authority

**Implementation:**
- Train on historical STIR data (2020–2025 Fed Funds and SOFR)
- Deploy model as a Python pickle loaded at startup
- Expose via `/regime/classify` endpoint
- Display classification probabilities in the dashboard

### 1.3 ML-Based Signal Scoring

**Current:** Strategy confidence is rule-based (additive from indicator checks).

**Planned:** ML model that scores signals based on:
- Historical signal performance (did similar signals lead to profitable outcomes?)
- Feature importance from gradient boosting
- Cross-sectional features (how do other contracts behave?)
- Time-of-day and day-of-week patterns

**Output:** Adjusted confidence score that blends rule-based and ML-based assessments.

### 1.4 Real-Time WebSocket Streaming

**Current:** Data is fetched on-demand via HTTP POST.

**Planned:** WebSocket streaming for real-time updates:
- Subscribe to symbol + timeframe pairs
- Receive bar updates as they form
- Auto-update indicators, signals, and ladders in real-time
- Push notifications for signal changes

**Implementation:**
- FastAPI WebSocket endpoints
- Frontend JavaScript WebSocket client
- Server-side pub/sub for efficient broadcasting
- Heartbeat and reconnection logic

### 1.5 Redis Cache Backend

**Current:** In-memory singleton cache (lost on restart).

**Planned:** Redis as shared cache backend:
- TTL-based expiration per data type
- Shared state across multiple workers
- Persistence across restarts
- Pub/sub for cache invalidation events

**Implementation:**
- `redis-py` async client
- `RedisCacheManager` implementing `CacheInterface`
- Feature flag: `CACHE_BACKEND=memory|redis` in `.env`
- Docker Compose Redis service

### 1.6 PostgreSQL Persistence

**Current:** No persistent storage.

**Planned:** PostgreSQL for:
- Replay session storage
- Annotated scenario library
- User preferences and layouts
- Audit trail of regime changes and signal history
- Historical signal performance tracking

**Implementation:**
- SQLAlchemy async ORM or raw asyncpg
- Alembic migrations
- Docker Compose PostgreSQL service

---

## 2. Phase 3 — Advanced Features

### 2.1 Portfolio Optimizer

**Current:** Single-instrument analysis.

**Planned:** Portfolio-level optimization:
- Correlation matrix across Fed Funds term structure
- Optimal spread portfolio for macro view
- DV01-neutral butterfly construction
- Risk budget allocation across positions
- Margin requirement estimation

### 2.2 Execution Integration (Read-Only)

**Current:** No broker connectivity.

**Planned:** Read-only connections to execution platforms:
- Pull current positions and fills
- Compare planned ladder with actual execution
- Calculate slippage from planned vs actual
- **No order submission** — planning tool only

### 2.3 Live P&L Tracking

**Current:** No position tracking.

**Planned:** Track paper positions:
- Record simulated entries from ladder levels
- Mark-to-market against live prices
- Track unrealized P&L per position
- Historical P&L curve

### 2.4 Multi-Desk Collaboration

**Current:** Single-user application.

**Planned:**
- User authentication (JWT or SAML)
- Role-based access (trader, quant, risk manager)
- Shared regime state with edit history
- Signal sharing and annotation
- Team dashboard with aggregated views

### 2.5 Custom Indicator SDK

**Current:** Indicators are hardcoded in the indicator engine.

**Planned:** Plugin system for custom indicators:
- Python function interface: `def my_indicator(series: OHLCVSeries, params: dict) -> IndicatorResult`
- YAML registration: add indicator to `strategy_settings.yaml`
- Auto-discovery of indicator plugins from a designated directory
- Hot-reload without server restart

### 2.6 Strategy Backtesting Framework

**Current:** Forward-looking signals only.

**Planned:** Historical backtesting:
- Walk-forward optimization
- In-sample / out-of-sample split
- Performance metrics: Sharpe, Sortino, max drawdown, win rate
- Strategy parameter sensitivity analysis
- Monte Carlo simulation for confidence intervals

---

## 3. Infrastructure Evolution

### 3.1 Monitoring & Observability

- **Prometheus metrics endpoint** (`/metrics`)
- **Grafana dashboards** for:
  - API latency percentiles
  - Cache hit/miss rates
  - Strategy signal frequency
  - Indicator computation times
  - External API call latency
- **Structured log aggregation** with ELK or Loki
- **Alerting** on error rates, latency spikes, health check failures

### 3.2 CI/CD Pipeline

- **GitHub Actions** for automated testing
- **Docker image builds** on merge to main
- **Container registry** (ECR, GCR, or self-hosted)
- **Staging environment** for pre-production testing
- **Blue/green deployment** for zero-downtime updates

### 3.3 Security Hardening

- API key authentication for all endpoints
- Rate limiting per client
- CORS restriction to specific domains
- Content Security Policy headers
- Docker image vulnerability scanning
- Secrets management (AWS Secrets Manager, HashiCorp Vault)

### 3.4 Horizontal Scaling

Current architecture supports vertical scaling (bigger server). For horizontal scaling:

```
┌──────────┐     ┌──────────┐
│  Nginx   │────>│ Worker 1 │──┐
│  (LB)    │────>│ Worker 2 │──├──> Redis (shared cache)
│          │────>│ Worker 3 │──┤    PostgreSQL (persistence)
└──────────┘     └──────────┘  │
                               └──> QH API (external)
```

Requirements:
- Redis for shared cache (mandatory)
- PostgreSQL for persistence
- Sticky sessions or stateless auth
- Health check-based load balancing

---

## 4. Data Enhancements

### 4.1 Alternative Data Sources

- CME direct feed integration
- Bloomberg Terminal API
- Refinitiv/LSEG data
- FRED (Federal Reserve Economic Data) for macro indicators
- OIS (Overnight Index Swap) curve data

### 4.2 Macro Event Calendar

- Automated FOMC meeting schedule loading
- NFP, CPI, PPI, GDP release dates
- Auto-suggest "event" regime on event days
- Countdown timer in dashboard

### 4.3 Options-Implied Volatility

- Fed Funds options implied vol surface
- Probability-weighted rate path from options pricing
- Vol surface overlay on chart
- Skew analysis for directional bias

---

## 5. Feature Priority Matrix

| Feature | Effort | Impact | Priority |
|---|---|---|---|
| Redis cache | Medium | High | P1 |
| PostgreSQL persistence | Medium | High | P1 |
| N-leg spreads | High | High | P1 |
| WebSocket streaming | High | High | P2 |
| AI regime classification | High | Medium | P2 |
| ML signal scoring | High | Medium | P2 |
| Portfolio optimizer | Very High | High | P2 |
| Backtesting framework | Very High | High | P2 |
| Execution integration | Medium | Medium | P3 |
| Custom indicator SDK | Medium | Medium | P3 |
| Multi-desk collaboration | Very High | Medium | P3 |
| Macro event calendar | Low | Medium | P1 |
| Prometheus metrics | Low | Medium | P1 |
| CI/CD pipeline | Medium | High | P1 |
