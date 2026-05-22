# Replay Engine Documentation

> Historical bar-by-bar playback, scenario analysis, workflows, and future simulation capabilities.

---

## 1. Overview

The Replay Engine provides historical bar-by-bar playback of market data, enabling traders to:

- Step through past market action one bar at a time
- Observe how indicators, signals, and ladders evolve in real-time
- Document trade scenarios and decision rationale
- Practice strategy application without live market risk
- Review past events (FOMC, NFP, CPI) and analyze platform behavior

---

## 2. Current Status

The Replay Engine is currently in **Phase 1** — the frontend page exists with the basic UI scaffold, and the backend infrastructure supports historical data replay. The full simulation loop is planned for Phase 2.

### What Exists Today

- **Frontend page:** `app/templates/replay/index.html` — UI for selecting symbol, timeframe, date range, and replay controls (play, pause, step forward, step backward)
- **Route:** `/replay` page route in `app/routes/pages.py`
- **Data foundation:** OHLCV series can be fetched for any historical range and cached. The indicator engine can recompute indicators on any sub-series.

### What Is Planned

- **ReplayEngine service** — Manages replay state, bar pointer, playback speed
- **Incremental indicator computation** — Recompute indicators as each new bar is added
- **Signal tracking** — Record which strategies would have fired at each bar
- **Ladder evolution** — Show how ladder levels shift as price evolves
- **Scenario journal** — Save annotated scenarios with notes and screenshots

---

## 3. Replay Architecture (Planned)

```
┌─────────────────────────────────────┐
│          ReplayEngine               │
│  ├── bar_pointer: int               │
│  ├── series: OHLCVSeries            │
│  ├── speed: float (bars/sec)        │
│  ├── state: playing | paused        │
│  └── history: list[ReplaySnapshot]  │
├─────────────────────────────────────┤
│  Methods:                           │
│  ├── load(symbol, tf, date_range)   │
│  ├── step_forward()                 │
│  ├── step_backward()                │
│  ├── play(speed)                    │
│  ├── pause()                        │
│  ├── get_current_view()             │
│  └── get_snapshot_at(bar_index)     │
└─────────────────────────────────────┘
```

### ReplaySnapshot

At each bar, the engine captures:

```python
class ReplaySnapshot(BaseModel):
    bar_index: int
    timestamp: datetime
    bar: OHLCVBar
    indicators: IndicatorSet       # Computed on bars[0:bar_index+1]
    signals: list[StrategySignal]  # Evaluated at this point
    regime: RegimeState
    ladder: AdaptiveLadder | None  # Generated at this point
    notes: str = ""
```

---

## 4. Replay Workflow

### Step 1: Load Historical Data

```
POST /replay/load
{
  "product_key": "fed_funds",
  "symbol": "FFN26",
  "timeframe": "1H",
  "start_date": "2026-01-01",
  "end_date": "2026-01-31"
}
```

The engine fetches the full historical series and stores it.

### Step 2: Initialize Replay

The bar pointer starts at bar 20 (minimum for most indicators). The first 20 bars are the warm-up period.

### Step 3: Step Through

Each step forward:
1. Advance bar pointer by 1
2. Recompute indicators on `bars[0:pointer+1]`
3. Evaluate all applicable strategies
4. Generate ladder if strategy fires a signal
5. Capture `ReplaySnapshot`
6. Update frontend (chart adds one candle, indicators update, signals refresh)

### Step 4: Review and Annotate

The trader can:
- Pause at any bar
- Add notes to the current snapshot
- Compare indicator values across time
- See which strategies would have fired
- View how the ladder would have been positioned

---

## 5. Frontend Controls (Planned)

```
┌─────────────────────────────────────────────────┐
│ ⏮ ◀  ⏸  ▶  ⏭  │  Speed: 1x  2x  5x  10x     │
│ Bar: 145/500  │  Time: 2026-01-15 14:00:00     │
├─────────────────────────────────────────────────┤
│                                                  │
│  [Candlestick Chart — bars up to current bar]   │
│  [Indicator overlays update with each step]     │
│                                                  │
├─────────────────────────────────────────────────┤
│  Active Signals:                                 │
│  - TrendFedRepricing: LONG (0.72)               │
│                                                  │
│  Ladder:                                         │
│  Level 1: 95.500 (7 lots)                       │
│  Level 2: 95.485 (11 lots)                      │
│  ...                                             │
├─────────────────────────────────────────────────┤
│  Notes: [text area for annotations]             │
└─────────────────────────────────────────────────┘
```

---

## 6. Event Replay Scenarios

The replay engine is particularly valuable for reviewing major Fed events:

### FOMC Decision Replay

1. Load 1M data for FOMC day (e.g., 2026-06-18)
2. Step through pre-announcement (10:00–14:00 ET)
3. Observe range compression and vol squeeze
4. Step through announcement bar (14:00 ET)
5. Observe ATR explosion and strategy signals
6. Step through aftermath (14:00–16:00 ET)
7. Document how EventMomentum and EventFade would have fired

### NFP Replay

1. Load 5M data for NFP Friday
2. Step through pre-release bars
3. Observe vol expansion and signal evolution
4. Document regime transition (range → event → trend)

---

## 7. Scenario Branching (Future)

Phase 2 will add scenario branching — the ability to fork the replay at any point and ask "what if":

- **What if the regime was set to TREND instead of RANGE?**
- **What if the macro bias was HAWKISH instead of NEUTRAL?**
- **What if we used 3 levels instead of 5?**

Each branch runs independently and can be compared side-by-side.

---

## 8. Data Persistence (Future)

Replay sessions and annotated scenarios will be persisted in PostgreSQL (Phase 2):

```sql
CREATE TABLE replay_sessions (
    id UUID PRIMARY KEY,
    symbol VARCHAR(20),
    timeframe VARCHAR(5),
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE replay_snapshots (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES replay_sessions(id),
    bar_index INT,
    timestamp TIMESTAMP,
    indicators_json JSONB,
    signals_json JSONB,
    ladder_json JSONB,
    notes TEXT
);
```

This enables building a library of reviewed scenarios for training and reference.
