# System Flow Documentation

> End-to-end data and decision flow from trader input to rendered output.

---

## 1. Overview

The platform transforms raw trader selections and market data into actionable strategy signals, adaptive entry ladders, and risk assessments through a deterministic, multi-stage pipeline.

```
Trader Input → Data Fetch → Normalization → Indicator Computation → Regime Processing
→ Strategy Evaluation → Ladder Generation → Risk Assessment → Frontend Rendering
```

Every stage is traceable. Every intermediate result is cached. Every output is a typed Pydantic model.

---

## 2. Trader Selections

The workflow begins when a trader configures the following inputs:

| Input | Source | Options |
|---|---|---|
| **Product** | `contracts.yaml` | `fed_funds` (ZQ), `sofr` (SR3) |
| **Symbol** | Product contracts list | Outrights: FFN26, FFQ26, etc. Spreads: FFN26-FFQ26, etc. |
| **Timeframe** | `strategy_settings.yaml` | 1M, 5M, 15M, 1H, 4H, 1D |
| **Strategy** | Strategy registry | trend_fed_repricing, mean_reversion_range, etc. |
| **Regime** | Manual selection | trend, range, volatility, event |
| **Macro Bias** | Manual selection | hawkish, dovish, neutral |

These selections flow into the system via API requests (`POST /market-data/ingest`, `POST /ladder/generate`, etc.) or frontend form submissions.

---

## 3. Stage 1: QH API Fetch

**Module:** `app/adapters/qh_adapter.py`
**Trigger:** `POST /market-data/fetch` or `POST /market-data/ingest`

### Process

1. `DataProvider.fetch_market_data()` receives the request with product_key, symbols, and timeframe.
2. It validates symbols against `contracts.yaml` — outrights must be in `contracts` list, spreads must be in `spreads` list.
3. For spread symbols (detected by `-`), it resolves both legs. E.g., `FFN26-FFQ26` resolves to `{FFN26, FFQ26}`.
4. `QHAdapter.fetch_multiple()` iterates over all unique legs and calls the external API for each.
5. The API URL is constructed as: `{QH_API_BASE_URL}/api/ohlc/?products={symbol}&timeIntervals={mapped_tf}`
6. Timeframe mapping: `1M→1min`, `5M→5min`, `15M→15min`, `1H→1hour`, `4H→4hour`, `1D→1day`

### Timestamp Parsing

The adapter handles multiple timestamp formats:
- ISO 8601: `2026-01-15T14:30:00Z`
- Unix seconds: `1737120600`
- Unix milliseconds: `1737120600000`
- Date-only: `2026-01-15`

### Field Mapping

The adapter tries multiple field name conventions per OHLCV field:
- Open: `Open`, `open`, `o`
- High: `High`, `high`, `h`
- Low: `Low`, `low`, `l`
- Close: `Close`, `close`, `c`
- Volume: `Volume`, `volume`, `v`
- Timestamp: `Timestamp`, `timestamp`, `t`

### Output

Each successful fetch produces an `OHLCVSeries` (list of `OHLCVBar` objects) which is immediately cached via `CacheManager.set_ohlcv(symbol, timeframe, series)`.

---

## 4. Stage 2: OHLCV Normalization

**Module:** `app/contracts/market_data.py`

Each `OHLCVBar` is a Pydantic model with validated fields:

```python
class OHLCVBar(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
```

`OHLCVSeries` wraps a list of bars with utility methods:
- `closes()` → `list[float]` — all close prices
- `highs()` → `list[float]` — all high prices
- `lows()` → `list[float]` — all low prices
- `volumes()` → `list[float]` — all volumes
- `latest` → last bar
- `is_empty` → True if no bars
- `length` → bar count

For **calendar spreads**, the `DataProvider` computes the spread value:

```
spread_bp = (front_price - back_price) × 100
```

This produces a `SpreadQuote` model with `front_leg`, `back_leg`, `front_price`, `back_price`, and `spread_bp` fields.

---

## 5. Stage 3: Indicator Computation

**Module:** `app/services/indicator_engine.py`
**Trigger:** `POST /market-data/ingest` (with `compute_indicators=true`) or on-demand from LadderEngine

### Process

`IndicatorEngine.compute_all(series)` is the orchestration method. It:

1. Validates the series is not empty
2. Creates an empty `IndicatorSet` for the symbol/timeframe
3. Iterates through all indicator categories, calling each computation method wrapped in `_safe()` (catches `InsufficientDataError` and logs warnings for unexpected errors)
4. Assigns results to the appropriate `IndicatorSet` field
5. Caches the complete `IndicatorSet` via `CacheManager.set_indicators()`

### Computation Order

```
Trend:       SMA(20,50), EMA(9,21), HMA(9), KAMA(10), VWAP, Anchored VWAP
Volatility:  ATR(14), NATR(14), HistVol(20), RealVol(20), BBW(20), DCW(20), Keltner(20)
Momentum:    RSI(14), StochRSI(14,14,3,3), MACD(12,26,9), ROC(14), Momentum(14), PPO(12,26,9)
Structure:   Donchian(20), Bollinger(20,2), RangeCompression(20), Expansion(20), SessionRange
Spread*:     SpreadZ(20), SpreadMeanDev(20), SpreadVel(5), SpreadAcc(5), CurveSlope(10), CurveMom(10)
Liquidity:   RelativeVolume(20), VolumeDelta
```

*Spread indicators are only computed when the symbol contains `-`.*

### Data Flow

```
OHLCVSeries.bars[] → numpy arrays → rolling window calculations → IndicatorResult → IndicatorSet → Cache
```

---

## 6. Stage 4: Regime Processing

**Module:** `app/services/regime_engine.py`
**Trigger:** `PUT /regime/update`

### Process

1. Trader manually selects regime (trend, range, volatility, event) and macro bias (hawkish, dovish, neutral) via the frontend.
2. The `RegimeEngine.set_regime()` method creates a `RegimeState` and stores it in cache.
3. The regime advisory (`GET /regime/suggest`) analyzes current indicators and provides a non-binding suggestion:
   - ATR expanding + EMA aligned → suggests "trend"
   - DCW compressed + price near Bollinger mean → suggests "range"
   - ATR at extremes → suggests "volatility"
   - No strong signals → suggests "range" (default)

### Impact on Downstream

The regime state affects:
- **Strategy engine** — Strategies check `applicable_regimes` before evaluation. A trend strategy won't fire in a range regime.
- **Ladder engine** — Spacing method changes by regime (ATR for trend, DCW for range, wider for volatility, single-entry for event).
- **Confidence scoring** — Regime alignment with strategy type boosts confidence.

---

## 7. Stage 5: Strategy Evaluation

**Module:** `app/services/strategy_engine.py`
**Trigger:** `POST /strategy/evaluate`

### Process

1. `StrategyEngine.evaluate()` receives product_key, symbols, timeframe, and optionally strategy names and regime override.
2. For each symbol:
   a. Retrieves cached `OHLCVSeries` and `IndicatorSet`
   b. Gets current `RegimeState`
   c. Filters strategies by:
      - Enabled in `strategy_settings.yaml`
      - Regime in `applicable_regimes`
      - Timeframe in `applicable_timeframes`
      - Spread-only strategies require spread symbols
   d. Calls each qualifying strategy's `evaluate()` method
   e. If a signal is produced, calls `build_entry_exit_plan()`
3. Results are collected into `StrategyEvalResult` objects.
4. Signal cards are cached for dashboard display.

### Signal Structure

Each strategy produces a `StrategySignal` with:
- `direction` — LONG, SHORT, FLAT
- `strength` — STRONG, MODERATE, WEAK
- `confidence` — 0.0 to 1.0
- `entry_price`, `stop_price`, `target_price`
- `risk_reward_ratio`
- `rationale` — human-readable explanation

---

## 8. Stage 6: Ladder Generation

**Module:** `app/services/ladder_engine.py`
**Trigger:** `POST /ladder/generate`

### Process

1. `LadderEngine.generate()` receives a `LadderRequest` with product_key, symbol, timeframe, strategy, optional direction and limits.
2. Resolves product config (tick sizes, tick values) from `contracts.yaml`.
3. Retrieves cached OHLCV and indicators. If indicators are missing, computes them on demand.
4. Reads current regime and macro bias from cache.
5. If direction is not specified, infers it from strategy type, EMA alignment, Bollinger position, or macro bias.
6. Extracts current ATR and DCW values.
7. Computes spacing based on regime:
   - **Trend:** `ATR × 0.5 × timeframe_mult`
   - **Range:** `DCW × 0.25 × timeframe_mult`
   - **Volatility:** `ATR × 1.2 × timeframe_mult`
   - **Event:** Single entry, no spacing
8. Builds N levels with lot distribution from the selected profile (pyramid, equal, front-loaded, back-loaded).
9. Computes stop from `avg_entry ± ATR × stop_mult` (direction-dependent).
10. Computes target_1 and target_2 from `avg_entry ± ATR × target_mult`.
11. Calculates total risk, total reward, and risk/reward ratio.
12. Scores MTF alignment and volatility percentile.
13. Returns a complete `AdaptiveLadder` model.

---

## 9. Stage 7: Risk Assessment

**Module:** `app/services/risk_engine.py`

### Process

For each generated ladder or manual trade plan:

1. Convert entry-to-stop distance to ticks: `distance / tick_size`
2. Convert ticks to dollars: `ticks × tick_value`
3. Compute position sizing from account risk: `max_risk_usd / risk_per_lot`
4. Apply slippage model: `estimated_slippage = ticks × slippage_factor`
5. Apply commission model: `commission = lots × commission_per_lot`
6. Compute net risk: `(risk_ticks + slippage_ticks) × tick_value × lots + commissions`
7. Compute R:R: `reward_distance / risk_distance`
8. Generate warnings if R:R < 1.0, risk exceeds limits, or volatility is extreme.

---

## 10. Stage 8: Frontend Rendering

**Module:** `app/routes/pages.py` + `app/templates/`

### Process

1. Page routes (`/`, `/strategy`, `/ladder`, `/risk`, `/replay`) load data from cache and pass it as Jinja2 template context.
2. Templates render HTML with Alpine.js reactive components.
3. User interactions trigger:
   - **API calls** via `fetch()` in Alpine.js methods (e.g., `generate()` in `ladder.js`)
   - **HTMX requests** for partial page updates (e.g., regime badge refresh)
4. Responses update the DOM reactively via Alpine.js `x-data` state.

### Ladder Page Flow

```
User selects product, symbol, timeframe, strategy → clicks "Generate Ladder"
  → Alpine.js calls POST /ladder/generate with JSON body
  → FastAPI validates LadderRequest
  → LadderEngine.generate() computes adaptive ladder
  → AdaptiveLadder JSON response
  → Alpine.js renders ladder table, risk/reward panel, context panel
```

---

## 11. Complete Pipeline Summary

```
┌──────────────────────────────────────────────────────────────────────────┐
│  1. Trader selects: product, symbol, timeframe, regime, macro bias      │
│  2. POST /market-data/ingest → QHAdapter fetches OHLCV → Cache         │
│  3. IndicatorEngine.compute_all() → 30+ indicators → Cache             │
│  4. PUT /regime/update → RegimeState → Cache                           │
│  5. POST /strategy/evaluate → 7 strategies filtered by regime/TF       │
│     → StrategySignals + EntryExitPlans → Cache                         │
│  6. POST /ladder/generate → LadderEngine reads indicators + regime     │
│     → Computes spacing, levels, lots, stop, targets, R:R               │
│     → AdaptiveLadder response                                          │
│  7. Frontend renders: chart, signals, ladder table, risk panel         │
└──────────────────────────────────────────────────────────────────────────┘
```
