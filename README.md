# Fed Funds Futures Strategy Planner V2

An institutional-style strategy planning and backtesting system for **CBOT Fed Funds (ZQ)** and **SOFR** futures. Built on real market microstructure rather than generic indicators — no ML, no regime detection, no prediction.

---

## What This Is

A complete planning and backtesting workstation that transforms raw OHLCV and Volume-at-Price data into executable trade plans with adaptive ladders, risk quantification, and realistic simulation.

**The core philosophy:**

> Signal → Entry → Exit is what retail does.
> Contract Context → Strategy Selection → Ladder Construction → Execution Plan → Realistic Backtest is what institutions do.

This system implements the second approach for STIR (Short Term Interest Rate) futures.

---

## How It Works — End to End

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INPUT                                │
│   Contract (FFN26) + Timeframe (1D) + Strategy (auto) + Risk    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              STEP 1 — CLASSIFY TRADE TYPE                        │
│   Is this an outright, calendar spread, or butterfly?            │
│   Strategy logic adapts: directional ladder vs spread reversion  │
│   vs asymmetric accumulation                                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│        STEP 2 — DETECT EXECUTION STATE                           │
│   From volume/price structure, classify:                         │
│     • Accumulation — repeated buying near level                  │
│     • Distribution — repeated selling near level                 │
│     • Balanced — symmetric participation                         │
│     • Impulse — one-sided directional execution                  │
│                                                                  │
│   These are NOT regimes. They are observable execution states    │
│   derived from vol concentration, directional ratio, range       │
│   compression, and VAP imbalance.                                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│        STEP 3 — SELECT STRATEGY FROM LIBRARY                     │
│   5 institutional templates (auto-selected or user-forced):      │
│                                                                  │
│   A. Mean Reversion — entry near extremes, exit near value       │
│   B. Continuation  — staggered entries in direction of flow      │
│   C. Acceptance Break — probe + add on confirmation              │
│   D. Failed Move   — fade extension with no participation        │
│   E. Relative Value — spread dislocation + mean target           │
│                                                                  │
│   Each template outputs: direction, entry_zone, target_zone,     │
│   stop multiplier, size profile, thesis, invalidation,           │
│   confirmation, and confidence factors.                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│         STEP 4 — BUILD ADAPTIVE LADDER                           │
│   Dynamic spacing (not fixed) based on:                          │
│     • ATR-scaled distances                                       │
│     • Contract tick constraints (min/max)                        │
│     • Risk budget (position sizing from stop distance)           │
│                                                                  │
│   Size profiles from config:                                     │
│     probe [1] | scale_in [1,2,3] | pyramid [3,2,1]              │
│     equal [2,2,2] | accumulation [1,2,3,2,1]                    │
│                                                                  │
│   Output:                                                        │
│     ENTRY: Level | Size | Confidence | Reason                    │
│     EXIT:  Level | Size | Reason                                 │
│     STOP:  Level                                                 │
│     RISK:  Max loss, tick exposure, R:R, hold estimate           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│      STEP 5 — CROSS CONTRACT CONTEXT                             │
│   Compare target contract to curve neighbors:                    │
│     • Relative 5-bar move                                        │
│     • Volume ratio (participation skew)                          │
│     • Directional alignment                                      │
│                                                                  │
│   Output: Score (0-100) + reasoning                              │
│   Used as weighting — never a hard filter.                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              EXECUTION PLAN OUTPUT                                │
│                                                                  │
│   • Trade type + Strategy name + Direction badges                │
│   • Trade thesis (plain English)                                 │
│   • Entry ladder (visual table)                                  │
│   • Exit ladder (visual table)                                   │
│   • Risk panel (max loss, ticks, R:R, capital, hold)             │
│   • Cross-contract score + neighbor detail                       │
│   • Execution notes (what invalidates / what confirms)           │
│   • Confidence factors (per-component scoring with bars)         │
│   • Execution Quality score (0-100)                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## The Backtest Engine

The V2 backtester is not a toy "hit target or stop" simulation. It models the full **trade lifecycle**:

```
planned → opened → scaled → trimmed → closed
```

### Execution Rules
- Entries fill **sequentially** (one level per bar maximum)
- Each entry is an independent fill at its own price + size
- Exits also fill sequentially, consuming position in tranches
- Stop hits close the **entire remaining position** at stop price
- Unfilled trades at end-of-data are closed at market

### Position Tracking
- Weighted average entry recalculated after each fill
- Running `realized_pnl` updated on every exit/stop
- `unrealized_pnl` tracked per bar
- Peak position recorded

### Risk Tracking
- **MAE** (Max Adverse Excursion) — worst tick drawdown from entry
- **MFE** (Max Favorable Excursion) — best tick move from entry
- Both tracked per-trade in ticks

### Metrics (16 total)
| Metric | What It Measures |
|--------|-----------------|
| Win Rate | % of profitable trades |
| Avg Return (ticks/USD) | Mean P&L per trade |
| Profit Factor | Gross profit / gross loss |
| Expectancy | Expected $ per trade |
| Sharpe | Risk-adjusted return (annualized) |
| Max Drawdown | Largest peak-to-trough decline |
| Avg Hold | Mean trade duration in bars |
| Avg MAE | How far trades go against you |
| Avg MFE | How far trades go in your favor |
| Risk Efficiency | Realized / MFE — are you capturing the move? |
| Ladder Efficiency | % of planned entry levels actually filled |
| Execution Quality | Composite score from ladder fill + win rate + Sharpe |
| Total P&L | Cumulative dollar return |
| Total Trades | Sample size |
| Wins / Losses | Distribution |
| Drawdown Curve | Underwater equity visualization |

---

## Project Structure

```
StrategyPlanner/
├── main.py                    FastAPI application + routes
├── strategy_config.json       All configuration (contracts, strategies, ladder, cross-contract)
├── requirements.txt           Python dependencies
├── .env.example               Environment variable template
│
├── services/
│   ├── planner.py             V2 Strategy Engine (640 lines)
│   │                          - classify_trade_type()
│   │                          - detect_execution_state()
│   │                          - select_strategy()
│   │                          - build_adaptive_ladder()
│   │                          - compute_cross_contract_score()
│   │                          - generate_plan()
│   │
│   ├── backtest.py            V2 Backtest Engine (424 lines)
│   │                          - LadderTrade class (lifecycle state machine)
│   │                          - run_backtest()
│   │                          - _build_summary() (16 metrics)
│   │
│   ├── indicators.py          Technical indicators
│   │                          - SMA, EMA, ATR, RSI, Bollinger, VWAP, Z-score
│   │
│   └── qh_api.py              Data layer
│                              - QuantHouse API client
│                              - Parquet caching
│                              - VAP parsing (POC, Value Area, Imbalance)
│                              - Spread synthesis
│
├── templates/
│   └── index.html             Jinja2 template — full V2 UI
│
├── static/
│   └── app.js                 Frontend JS — chart, plan render, backtest render
│
└── data_cache/                Parquet cache directory (gitignored)
```

---

## Component Deep-Dive

### `services/planner.py` — The Strategy Engine

The brain of the system. Takes raw market data and produces an executable trade plan.

**Key design decisions:**
- **No regime detection** — regimes are subjective and over-fitted. Instead, detect objective *execution states* from measurable structure (volume concentration, directional bar ratio, range compression).
- **Strategy templates are action plans, not signals** — each template outputs everything needed to execute: entry zone, target zone, stop multiplier, size profile, thesis, and invalidation criteria.
- **Adaptive spacing** — ladder levels are not equally spaced. Spacing scales with ATR, respects tick constraints, and adapts to the distance between current price and the entry zone.
- **Cross-contract context as weighting** — neighboring contracts on the curve provide alignment/divergence information. This is used to boost or dampen confidence, never to filter.

### `services/backtest.py` — The Simulation Engine

Models how a ladder trade actually behaves when executed bar-by-bar.

**Key design decisions:**
- **`LadderTrade` class** — encapsulates the full lifecycle with methods for `try_fill_entries()`, `try_fill_exits()`, `check_stop()`, `update_mae_mfe()`, and `close_at_market()`.
- **Sequential fills** — mirrors reality. You don't get filled at all levels simultaneously. One entry per bar maximum.
- **Cooldown period** — 2 bars between trades prevents over-trading in choppy conditions.
- **Walk-forward** — each signal is generated from only data available at that point. No lookahead.

### `services/indicators.py` — Technical Indicators

Utility layer providing SMA, EMA, ATR, RSI, Bollinger Bands, VWAP, and Z-score. These feed into the execution state detection and strategy selection. They are **inputs to decisions, not signals themselves**.

### `services/qh_api.py` — Data Layer

Handles all interaction with QuantHouse API:
- OHLCV fetch with configurable timeframes
- Volume-at-Price (VAP) data fetch and parsing
- POC (Point of Control), Value Area calculation
- VAP buy/sell imbalance
- Spread series synthesis (leg1 - leg2)
- Parquet caching with configurable TTL

### `strategy_config.json` — Configuration

Single source of truth for:
- **Contracts** — outrights (FFN26 through FFJ27), spreads (3), butterflies (1)
- **Strategies** — 5 institutional templates
- **Tick economics** — tick size (0.005), tick value ($20.835), multiplier (4167)
- **Ladder settings** — max levels, spacing bounds, 5 named size profiles
- **Cross-contract map** — which contracts are neighbors on the curve

### `static/app.js` — Frontend

Dark-mode institutional UI with three tabs:
1. **Plan** — trade thesis banner, entry/exit ladder tables (level, size, confidence, reason), risk panel, cross-contract score, execution notes, confidence factor bars
2. **Chart** — Lightweight Charts with OHLCV + toggleable indicators (VWAP, EMA, BB, SMA) + RSI sub-chart
3. **Backtest** — 10 metric cards (2 rows), equity curve canvas, drawdown curve canvas, MAE/MFE summary, full trade log table

---

## Research Thinking

### Why These 5 Strategies?

They map to the fundamental ways institutional STIR traders express views:

| Strategy | Market Condition | Institutional Analog |
|----------|-----------------|---------------------|
| Mean Reversion | Extended from value | Selling premium, fading flows |
| Continuation | Directional momentum | Following central bank re-pricing |
| Acceptance Break | New level accepting | Structural break in rate expectations |
| Failed Move | Thin extension | Failed auction, no participation at extreme |
| Relative Value | Spread dislocation | Curve trades, calendar rolls |

### Why Execution States Instead of Regimes?

Regimes (Trend, Mean Reversion, Volatile) are **ex-post classifications** — you only know the regime after it's over. Execution states are **observable in real-time**:

- **Volume concentration** — is volume clustered (balanced) or dispersed (impulse)?
- **Directional ratio** — what % of bars are up vs down?
- **Range ratio** — is the range expanding or compressed relative to ATR?
- **VAP imbalance** — are buyers or sellers dominating at-price?

These metrics directly inform *what kind of trade to take*, not *what direction*.

### Why Adaptive Ladders?

Static ladders (equal spacing, equal size) fail because:
1. They don't account for volatility — 3 tick spacing means nothing if ATR is 2 ticks vs 20 ticks
2. They don't scale risk — a 5-lot probe and a 5-lot final add have very different risk profiles
3. They don't have conviction gradients — deeper fills at better prices should carry more confidence

The V2 ladder system uses:
- **ATR-scaled spacing** clamped between min/max tick constraints
- **Named size profiles** that match the strategy intent (probe = light, pyramid = front-loaded, accumulation = center-heavy)
- **Risk-derived lot sizing** — total position is constrained by `risk_usd / (stop_ticks * tick_value)`

### Why Cross-Contract Context?

STIR futures trade on a **curve**. What happens to FFN26 is influenced by what FFQ26 and FFU26 are doing:
- If all contracts move together → alignment → higher confidence
- If your contract moves but neighbors don't → divergence → lower confidence
- If volume skews toward your contract → participation → conviction boost

This is not a signal. It's a contextual weight applied to confidence scoring.

### Why This Backtest Design?

Most backtests are unrealistic because they:
- Fill all entries at once (doesn't happen)
- Use a single entry/exit (misses ladder dynamics)
- Don't track how far trades go against you before winning (MAE)
- Don't measure execution efficiency

The `LadderTrade` state machine models reality:
- You get filled **sequentially** as price reaches each level
- Some trades only fill 1 of 3 entries (ladder efficiency < 100%)
- Exits happen in tranches (trim, reduce, take profit)
- MAE/MFE tell you if your entries were good (low MAE) and if your exits captured the move (high risk efficiency)

---

## Quick Start

```bash
# Clone and install
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your QuantHouse credentials:
# QH_BASE_URL=https://your-api-url
# QH_TOKEN=your-token

# Run
python main.py
# → http://localhost:8000
```

### Usage Flow
1. Select a contract (outright, spread, or butterfly)
2. Choose timeframe (5M to 1D)
3. Set strategy to `auto` (engine detects best fit) or force one
4. Set risk budget in USD
5. Click **Generate Plan** → full execution plan with ladders
6. Click **Load Chart** → OHLCV with indicators
7. Click **Run Backtest** → realistic simulation with 16 metrics

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + Uvicorn |
| Data | QuantHouse API + Parquet caching |
| Computation | Pandas + NumPy |
| Frontend | Vanilla JS + TailwindCSS + Lightweight Charts |
| Templating | Jinja2 |

No ML. No TensorFlow. No scikit-learn. No external signal providers.
Just market structure, volume analysis, and institutional execution logic.

---

## Constraints (By Design)

- **No ML** — not enough edge in STIR for ML to be meaningful without overfitting
- **No regime detection** — replaced with observable execution states
- **No prediction** — system plans *reactions*, not *forecasts*
- **No generic indicators as signals** — RSI/BB/VWAP are inputs to execution state detection, not trade triggers
- **No hard filters** — cross-contract context and confidence factors are weights, not gates

---

## What V2 Changed From V1

| Aspect | V1 | V2 |
|--------|----|----|
| Signal | Composite score from trend/momentum/vol/VWAP/VAP | Execution state detection |
| Strategy | User picks regime → weighted scoring | Auto-selects from 5 templates based on structure |
| Ladder | 3 entries, equal spacing, static | Adaptive spacing, named size profiles, risk-constrained |
| Output | Score + direction + basic levels | Full thesis + ladders + risk + cross-contract + notes |
| Backtest | Entry/stop/target binary | Lifecycle state machine with sequential fills |
| Metrics | Win rate + PF + drawdown | 16 metrics including MAE/MFE/ladder efficiency/Sharpe |
| UI | Signal banner + basic ladder list | Institutional layout with thesis, tables, confidence bars |

---

## License

Private — not for redistribution.
