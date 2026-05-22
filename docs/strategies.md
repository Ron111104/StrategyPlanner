# Strategy Documentation

> Complete reference for all seven institutional strategies: purpose, logic, conditions, regime gating, and ladder behavior.

---

## 1. Strategy Architecture

All strategies inherit from `BaseStrategy` (`app/strategies/base.py`) and implement two methods:

```python
def evaluate(self, series, indicators, regime, product_config) -> Optional[StrategySignal]
def build_entry_exit_plan(self, signal, series, indicators, product_config) -> Optional[EntryExitPlan]
```

### Strategy Lifecycle

1. `StrategyEngine` loads all registered strategies from `app/strategies/__init__.py`
2. For each evaluation request, it filters strategies by:
   - `enabled` flag in `strategy_settings.yaml`
   - `applicable_regimes` contains current regime
   - `applicable_timeframes` contains requested timeframe
   - `spread_only` matches symbol type (spread symbols contain `-`)
3. Each qualifying strategy's `evaluate()` is called
4. If evaluation returns a `StrategySignal`, `build_entry_exit_plan()` is called
5. Results are aggregated and cached

### BaseStrategy.should_disable()

Every strategy calls `should_disable()` before evaluation. This method checks:
- Series is not empty
- Series has sufficient bars (>= minimum required for indicators)
- Regime is in `applicable_regimes`

If disabled, the strategy returns `None` immediately.

### Confidence Classification

All strategies use `_classify_strength()`:
- confidence >= 0.7 → `STRONG`
- confidence >= 0.5 → `MODERATE`
- confidence < 0.5 → `WEAK`

---

## 2. Trend Fed Repricing

**File:** `app/strategies/trend_fed_repricing.py`
**Class:** `TrendFedRepricing`
**Name:** `trend_fed_repricing`

### Purpose

Captures directional repricing moves in Fed Funds futures when the market is trending due to shifts in Fed policy expectations. This is the primary trend-following strategy for macro rate repricing events.

### Market Context

This strategy fires when the FOMC has shifted its dot plot, when employment or inflation data forces a repricing of the rate path, or when market participants are adjusting positions in a sustained directional move.

### Regime Requirements

- **Required regime:** `trend`
- **Applicable timeframes:** 1H, 4H, 1D

### Entry Conditions

The strategy accumulates confidence from four independent checks:

| Check | Condition | Confidence |
|---|---|---|
| **EMA Alignment** | EMA(9) > EMA(21) → LONG; EMA(9) < EMA(21) → SHORT | +0.30 |
| **ATR Expansion** | Recent ATR > 1.2× ATR from 5 bars ago | +0.20 |
| **Donchian Breakout** | Price at Donchian upper (LONG) or lower (SHORT) | +0.20 |
| **Macro Bias Alignment** | Dovish + LONG; or Hawkish + SHORT | +0.15 |

**Minimum confidence to fire:** 0.50
**Direction required:** Must not be FLAT

### Exit Logic (Entry/Exit Plan)

| Level | Calculation |
|---|---|
| **Entry** | Current close |
| **Stop** | Entry ± 2.0 × ATR (against direction) |
| **Primary Target** | Entry ± 3.0 × ATR (with direction) |
| **Secondary Target** | Entry ± 4.0 × ATR |
| **Tertiary Target** | Entry ± 5.0 × ATR |

Risk/Reward = |target - entry| / |entry - stop| = 3.0 / 2.0 = **1.50**

### Failure Conditions

- No EMA alignment (both EMAs absent or equal)
- ATR not available (insufficient data)
- Regime is not `trend`
- Confidence < 0.50
- Direction remains FLAT

### Ideal Market Conditions

- Clear FOMC-driven repricing
- EMA(9) firmly above/below EMA(21)
- ATR expanding (accelerating trend)
- Price at Donchian extreme
- Macro bias confirming direction

### Ladder Behavior

When this strategy feeds into the ladder engine:
- Spacing uses ATR × 0.5 × timeframe_multiplier (trend regime)
- Lot profile defaults to `pyramid` (more lots at first level)
- Stop at avg_entry ± ATR × 2.0
- Target_1 at avg_entry ± ATR × 3.0

---

## 3. Mean Reversion Range

**File:** `app/strategies/mean_reversion_range.py`
**Class:** `MeanReversionRange`
**Name:** `mean_reversion_range`

### Purpose

Profits from price returning to the mean in range-bound markets. When Fed Funds are consolidating between FOMC meetings with no clear directional catalyst, prices oscillate within Bollinger Bands, and this strategy fades moves to the extremes.

### Regime Requirements

- **Required regime:** `range`
- **Applicable timeframes:** 15M, 1H, 4H

### Entry Conditions

| Check | Condition | Confidence |
|---|---|---|
| **Bollinger Extreme** | Position > 0.95 → SHORT (+0.40); Position < 0.05 → LONG (+0.40) | +0.25 to +0.40 |
| **Bollinger Near-Extreme** | Position > 0.80 → SHORT; Position < 0.20 → LONG | +0.25 |
| **SMA(20) Deviation** | |deviation| > 0.2% from SMA(20), direction aligns | +0.15 |
| **DCW Compression** | Recent DCW / avg DCW < 0.70 | +0.20 |

**Minimum confidence to fire:** 0.40

Bollinger position formula:
```
position = (close - lower_band) / (upper_band - lower_band)
```

### Exit Logic

| Level | Calculation |
|---|---|
| **Entry** | Current close |
| **Stop** | Entry ± 1.5 × ATR |
| **Primary Target** | Entry ± 2.0 × ATR |
| **Secondary Target** | SMA(20) value (the mean) |

Risk/Reward = 2.0 / 1.5 = **1.33**

### Failure Conditions

- No Bollinger data
- Price not at extremes (position between 0.20 and 0.80)
- DCW expanding (not a range market)
- Regime is not `range`

### Ladder Behavior

- Spacing uses DCW × 0.25 × timeframe_multiplier (range regime)
- Tighter spacing reflects narrower expected range
- Lot profile can be `equal` for range strategies

---

## 4. Event Momentum

**File:** `app/strategies/event_momentum.py`
**Class:** `EventMomentum`
**Name:** `event_momentum`

### Purpose

Captures the initial momentum burst following a significant macro event (FOMC decision, NFP, CPI). In the minutes and hours after a surprise data release, Fed Funds futures can reprice aggressively. This strategy rides that momentum.

### Regime Requirements

- **Required regime:** `event`
- **Applicable timeframes:** 1M, 5M, 15M

### Entry Logic

Event momentum strategies look for:
- ATR spike indicating event impact
- Volume surge confirming participation
- Directional move aligned with macro bias
- Momentum indicator confirmation

### Ladder Behavior

- **Single entry** (no multi-level ladder) — event regime forces `event_single_entry: true`
- Tight stop (1.0 × ATR)
- Extended targets (3.0–4.0 × ATR)

---

## 5. Event Fade

**File:** `app/strategies/event_fade.py`
**Class:** `EventFade`
**Name:** `event_fade`

### Purpose

Fades the initial overreaction to a macro event. After the first momentum burst, prices often retrace as the market digests the actual implications. This strategy enters against the event move once momentum decelerates.

### Regime Requirements

- **Required regime:** `event`
- **Applicable timeframes:** 5M, 15M, 1H

### Entry Logic

- Identifies overextended post-event move
- Looks for momentum deceleration (declining ATR, RSI extreme)
- Enters counter-trend with tight risk

### Risk Profile

- Tighter stops than momentum (event can resume)
- Conservative targets (partial retracement, not full reversal)
- Lower confidence threshold due to higher uncertainty

---

## 6. Volatility Fade

**File:** `app/strategies/volatility_fade.py`
**Class:** `VolatilityFade`
**Name:** `volatility_fade`

### Purpose

Profits from the mean-reversion of volatility itself. After a volatility spike (ATR at extremes), volatility tends to contract. This strategy positions for the return to normal volatility levels, which typically favors range-bound price action.

### Regime Requirements

- **Required regime:** `volatility`
- **Applicable timeframes:** 15M, 1H, 4H

### Entry Logic

- ATR at high percentile (indicating volatility spike)
- Bollinger Width expanded (price has moved far from mean)
- Enter toward the mean (Bollinger middle or SMA)
- Confidence scales with the magnitude of the vol spike

### Ladder Behavior

- Wider spacing (ATR × 1.2 × timeframe_multiplier) due to elevated volatility
- More conservative lot sizing
- Wider stops to accommodate volatility

---

## 7. Curve Steepener

**File:** `app/strategies/curve_steepener.py`
**Class:** `CurveSteepener`
**Name:** `curve_steepener`

### Purpose

Spread strategy that profits from the yield curve steepening (front month pricing lower rates relative to back month). In Fed Funds terms, this means the front month price rises relative to the back month (spread becomes more positive or less negative).

### Regime Requirements

- **Required regime:** `trend`, `range`
- **Applicable timeframes:** 1H, 4H, 1D
- **Spread only:** Yes — only evaluated for spread symbols

### Entry Logic

- Spread Z-score indicates the spread is compressed (room to steepen)
- Curve slope is positive (steepening trend)
- Macro bias supports steepening (dovish = front month rates drop faster)

### Trade Expression

Buy the spread: Long front month, short back month.

---

## 8. Curve Flattener

**File:** `app/strategies/curve_flattener.py`
**Class:** `CurveFlattener`
**Name:** `curve_flattener`

### Purpose

Spread strategy that profits from the yield curve flattening (front month pricing higher rates relative to back month). The spread becomes more negative.

### Regime Requirements

- **Required regime:** `trend`, `range`
- **Applicable timeframes:** 1H, 4H, 1D
- **Spread only:** Yes

### Entry Logic

- Spread Z-score indicates the spread is extended (room to flatten)
- Curve slope is negative (flattening trend)
- Macro bias supports flattening (hawkish = front month rates rise faster)

### Trade Expression

Sell the spread: Short front month, long back month.

---

## 9. Strategy Comparison Matrix

| Strategy | Regime | Timeframes | Instruments | Min Confidence | Stop (ATR×) | Target (ATR×) | R:R |
|---|---|---|---|---|---|---|---|
| Trend Fed Repricing | trend | 1H, 4H, 1D | outrights | 0.50 | 2.0 | 3.0 | 1.50 |
| Mean Reversion Range | range | 15M, 1H, 4H | outrights | 0.40 | 1.5 | 2.0 | 1.33 |
| Event Momentum | event | 1M, 5M, 15M | outrights | 0.50 | 1.0 | 3.0 | 3.00 |
| Event Fade | event | 5M, 15M, 1H | outrights | 0.50 | 1.0 | 1.5 | 1.50 |
| Volatility Fade | volatility | 15M, 1H, 4H | outrights | 0.50 | 2.0 | 2.5 | 1.25 |
| Curve Steepener | trend, range | 1H, 4H, 1D | spreads | 0.50 | spread-based | spread-based | varies |
| Curve Flattener | trend, range | 1H, 4H, 1D | spreads | 0.50 | spread-based | spread-based | varies |

---

## 10. Strategy Extensibility

To add a new strategy:

1. Create `app/strategies/my_strategy.py` inheriting from `BaseStrategy`
2. Implement `evaluate()` and `build_entry_exit_plan()`
3. Register in `app/strategies/__init__.py`
4. Add configuration in `strategy_settings.yaml`:
```yaml
strategies:
  my_strategy:
    enabled: true
    priority: 8
    applicable_regimes: [trend]
    applicable_timeframes: [1H, 4H]
    spread_only: false
```
5. Add corresponding entry in the ladder engine's `STRATEGY_DEFAULTS` dict if custom stop/target multipliers are needed.

No other code changes required. The `StrategyEngine` dynamically discovers and evaluates all registered strategies.
