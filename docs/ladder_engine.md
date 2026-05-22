# Ladder Engine Documentation

> Deep technical reference for the Adaptive Strategy Ladder Engine — the core differentiator of the platform.

---

## 1. Why Ladders Exist

Institutional traders do not enter positions at a single price. They **ladder into positions** across multiple price levels for several critical reasons:

- **Improved average entry** — By distributing entries across a range, the weighted average entry is better than a single entry if the market moves adversely before reversing.
- **Adverse selection mitigation** — A single entry at a single price is maximally exposed to adverse selection. Laddering reduces this risk.
- **Confidence scaling** — More lots are allocated at better prices (further from current market), reflecting higher conviction at better levels.
- **Volatility accommodation** — In volatile markets, a single entry may be hit and immediately stopped out. Ladder entries at wider intervals survive volatility noise.
- **Position sizing discipline** — Laddering enforces a pre-planned position build rather than impulsive full-size entry.

### Traditional vs. Adaptive Laddering

| Traditional | Adaptive (This Platform) |
|---|---|
| Trader manually picks prices | Engine computes prices from ATR, DCW, regime |
| Fixed spacing (e.g., every 5 ticks) | Dynamic spacing from volatility and timeframe |
| Fixed lot sizes | Profile-based distribution (pyramid, equal, etc.) |
| Manual stop/target | Auto-computed from ATR × strategy multiplier |
| No timeframe adjustment | Spacing scales with timeframe (1M=0.3× to 1D=2.5×) |
| No regime awareness | Regime changes spacing method entirely |

---

## 2. Ladder Engine Architecture

**File:** `app/services/ladder_engine.py`
**Class:** `LadderEngine`

### Dependencies

```
LadderEngine
  ├── CacheManager (OHLCV, indicators, regime, account)
  ├── IndicatorEngine (on-demand computation)
  ├── ConfigLoader (contracts.yaml for tick sizes, strategy_settings.yaml for ladder config)
  └── Constants: REGIME_SPACING, LOT_PROFILES, STRATEGY_DEFAULTS, TIMEFRAME_MULT
```

### Generation Pipeline

```
LadderRequest
  │
  ├── 1. Resolve product config (tick_size, tick_value)
  ├── 2. Get cached OHLCV series
  ├── 3. Get or compute indicators
  ├── 4. Get regime state
  ├── 5. Get account limits (max_lots, max_risk)
  ├── 6. Determine direction (explicit or inferred)
  ├── 7. Extract current ATR and DCW values
  ├── 8. Compute spacing from regime + timeframe
  ├── 9. Build N levels with lot distribution
  ├── 10. Compute weighted average entry
  ├── 11. Compute stop (avg_entry ± ATR × stop_mult)
  ├── 12. Compute target_1 and target_2
  ├── 13. Compute risk/reward ratio
  ├── 14. Score MTF alignment
  ├── 15. Compute volatility percentile
  ├── 16. Compute overall confidence
  │
  ▼
AdaptiveLadder (complete output)
```

---

## 3. Spacing Logic

Spacing is the price distance between ladder levels. It is computed from three inputs: **regime** (which determines the source), **volatility measure** (ATR or DCW), and **timeframe** (which scales the spacing).

### Regime-Based Spacing

| Regime | Source | Multiplier | Formula | Rationale |
|---|---|---|---|---|
| **Trend** | ATR | 0.5 | `ATR × 0.5 × TF_mult` | Trending markets: moderate spacing, follow the move |
| **Range** | DCW | 0.25 | `DCW × 0.25 × TF_mult` | Range markets: tighter spacing within the channel |
| **Volatility** | ATR | 1.2 | `ATR × 1.2 × TF_mult` | High vol: wider spacing to survive noise |
| **Event** | NONE | 0.0 | Single entry, no spacing | Event: immediate entry, no ladder |

### Timeframe Multipliers

| Timeframe | Multiplier | Effect |
|---|---|---|
| 1M | 0.3 | Very tight spacing (scalping) |
| 5M | 0.5 | Tight spacing (intraday) |
| 15M | 0.7 | Moderate-tight |
| 1H | 1.0 | Base spacing (reference) |
| 4H | 1.5 | Wider spacing (swing) |
| 1D | 2.5 | Wide spacing (position) |

### Spacing Computation Example

**Setup:** Trend regime, 1H timeframe, ATR = 0.025, tick_size = 0.005

```
raw_spacing = ATR × 0.5 = 0.025 × 0.5 = 0.0125
tf_adjusted = 0.0125 × 1.0 = 0.0125
tick_snapped = round(0.0125 / 0.005) × 0.005 = 0.015  (3 ticks)
```

**Setup:** Range regime, 4H timeframe, DCW = 0.080, tick_size = 0.005

```
raw_spacing = DCW × 0.25 = 0.080 × 0.25 = 0.020
tf_adjusted = 0.020 × 1.5 = 0.030
tick_snapped = round(0.030 / 0.005) × 0.005 = 0.030  (6 ticks)
```

### Fallback Logic

If the primary source is unavailable:
1. If ATR source but ATR is None → try DCW × 0.25
2. If DCW source but DCW is None → try ATR × 0.5
3. If both None → `tick_size × 3` (minimum viable spacing)

### Tick Grid Snapping

All spacing values are rounded to the nearest tick increment:
```python
spacing = max(tick_size, round(spacing / tick_size) * tick_size)
```
This ensures all ladder prices land on valid tick boundaries. Minimum spacing is one tick.

---

## 4. Level Construction

### Direction Sign Convention

For **long** entries (including steepener spreads), ladder levels are placed **below** the current price (buying on dips):
```
Level 1: entry_ref - 0 × spacing = current price
Level 2: entry_ref - 1 × spacing
Level 3: entry_ref - 2 × spacing
...
```

For **short** entries (including flattener spreads), ladder levels are placed **above** the current price:
```
Level 1: entry_ref + 0 × spacing = current price
Level 2: entry_ref + 1 × spacing
Level 3: entry_ref + 2 × spacing
...
```

### Level Count

- Default max: 5 levels (from `ladder.max_levels` in config)
- Event regime: forced to 1 level (single entry)
- Request can override: `LadderRequest.max_levels`
- Actual: `min(request.max_levels, config.max_levels)`

---

## 5. Lot Distribution Profiles

The lot distribution profile determines how lots are allocated across ladder levels.

### Profile Definitions

| Profile | Weights (5-level) | Description |
|---|---|---|
| **pyramid** | [1.0, 1.5, 2.5, 3.5, 5.0] | More lots at deeper levels (better prices) |
| **equal** | [1.0, 1.0, 1.0, 1.0, 1.0] | Equal lots at each level |
| **front_loaded** | [3.0, 2.5, 2.0, 1.5, 1.0] | More lots at first level (aggressive) |
| **back_loaded** | [1.0, 1.5, 2.0, 2.5, 3.0] | More lots at deeper levels (similar to pyramid) |

### Lot Calculation

```python
total_weight = sum(profile_weights)
lots_at_level = max(1, int((weight / total_weight) * max_lots))
```

### Strategy → Profile Mapping

| Strategy | Default Profile | Rationale |
|---|---|---|
| trend_fed_repricing | pyramid | Scale into trend, more at better prices |
| mean_reversion_range | front_loaded | Aggressive entry near reversal point |
| event_momentum | equal | Single entry (event regime) |
| event_fade | equal | Single entry (event regime) |
| volatility_fade | front_loaded | Aggressive initial entry |
| curve_steepener | pyramid | Scale into spread position |
| curve_flattener | pyramid | Scale into spread position |

### Pyramid Example (5 levels, max_lots=100)

| Level | Weight | Lots | Cumulative |
|---|---|---|---|
| 1 | 1.0 / 13.5 = 7.4% | 7 | 7 |
| 2 | 1.5 / 13.5 = 11.1% | 11 | 18 |
| 3 | 2.5 / 13.5 = 18.5% | 18 | 36 |
| 4 | 3.5 / 13.5 = 25.9% | 25 | 61 |
| 5 | 5.0 / 13.5 = 37.0% | 37 | 98 |

---

## 6. Direction Inference

When the `LadderRequest` does not specify a direction, the engine infers it through a priority chain:

### Inference Priority

1. **Curve strategies** — Fixed: `curve_steepener` → "steepener", `curve_flattener` → "flattener"
2. **Event fade** — Opposes the last bar's move: if close[-1] > close[-2] → "short"
3. **Mean reversion** — Opposes Bollinger position: if close < Bollinger middle → "long"
4. **EMA alignment** — If EMA(9) > EMA(21) → "long", else "short"
5. **Macro bias fallback** — If dovish → "long", if hawkish → "short"
6. **Final fallback** — "long"

---

## 7. Stop and Target Computation

### Stop Calculation

```
stop = avg_entry ± ATR × stop_atr_mult
```

Where ± depends on direction:
- Long/steepener: stop = avg_entry - ATR × mult (below entry)
- Short/flattener: stop = avg_entry + ATR × mult (above entry)

### Target Calculation

```
target_1 = avg_entry ± ATR × target_atr_mult[0]
target_2 = avg_entry ± ATR × target_atr_mult[1]
```

Where ± is with direction (opposite of stop).

### Strategy-Specific Multipliers

| Strategy | Stop (ATR×) | Target 1 (ATR×) | Target 2 (ATR×) |
|---|---|---|---|
| trend_fed_repricing | 1.5 | 2.0 | 4.0 |
| mean_reversion_range | 1.0 | 1.5 | 2.5 |
| event_momentum | 2.0 | 2.5 | 5.0 |
| event_fade | 1.5 | 1.0 | 2.0 |
| volatility_fade | 1.2 | 1.5 | 3.0 |
| curve_steepener | 1.5 | 2.0 | 4.0 |
| curve_flattener | 1.5 | 2.0 | 4.0 |

### ATR Source Fallback

If ATR is unavailable, the engine uses DCW. If both are unavailable, it uses the computed spacing value. This ensures stop/target computation never fails.

---

## 8. Average Entry Calculation

```python
avg_entry = Σ(level_price × level_lots) / Σ(level_lots)
```

This is the lot-weighted average of all ladder level prices. For a pyramid profile with deeper levels getting more lots, the average entry will be closer to the deeper levels.

### Example

| Level | Price | Lots | Price × Lots |
|---|---|---|---|
| 1 | 95.500 | 7 | 668.5 |
| 2 | 95.485 | 11 | 1050.335 |
| 3 | 95.470 | 18 | 1718.46 |
| 4 | 95.455 | 25 | 2386.375 |
| 5 | 95.440 | 37 | 3531.28 |

Average entry = 9354.95 / 98 = **95.4587** (between level 3 and 4)

---

## 9. Risk/Reward Calculation

```
stop_distance = |avg_entry - stop|
target_distance = |target_1 - avg_entry|
R:R = target_distance / stop_distance

stop_ticks = stop_distance / tick_size
total_risk_usd = stop_ticks × tick_value × total_lots
total_reward_usd = (target_distance / tick_size) × tick_value × total_lots
```

### Example

Using the average entry above (95.4587), with trend strategy:
```
stop = 95.4587 - 0.025 × 1.5 = 95.4212
target_1 = 95.4587 + 0.025 × 2.0 = 95.5087
stop_distance = 0.0375
target_distance = 0.050
R:R = 0.050 / 0.0375 = 1.33
stop_ticks = 0.0375 / 0.005 = 7.5
total_risk_usd = 7.5 × $20.835 × 98 = $15,311.73
```

---

## 10. Volatility Percentile

The engine computes where the current ATR sits relative to the last 100 ATR values (or all available if fewer):

```python
lookback = atr_values[-100:]  # or all available
rank = count(v <= current_atr for v in lookback)
percentile = rank / len(lookback) × 100
```

This is used for confidence adjustment:
- Percentile between 20–80 (normal volatility) → +0.10 confidence
- Extreme volatility (< 20 or > 80) → no bonus

---

## 11. MTF Alignment

The engine checks higher timeframes for EMA alignment:

```
For each higher timeframe (above current):
  - Get cached indicators
  - Check EMA(9) vs EMA(21)
  - If aligned with trade direction → +1 aligned
  - Count checked

MTF score = aligned / checked  (0.0 to 1.0)
```

MTF score > 0.5 → +0.10 confidence boost.

---

## 12. Confidence Scoring

Final confidence is computed from:

```
base = 0.60
+ 0.10 if vol_percentile between 20 and 80
+ 0.10 if mtf_alignment > 0.50
+ 0.05 if regime is trend or range
max = 1.00
```

---

## 13. Complete Worked Example

**Input:**
- Symbol: FFN26, Timeframe: 1H, Strategy: trend_fed_repricing
- Current close: 95.500, ATR: 0.025, DCW: 0.080
- Regime: trend, Macro bias: dovish
- Max lots: 100, Tick size: 0.005, Tick value: $20.835

**Step 1: Spacing**
```
regime = trend → source = ATR, mult = 0.5
raw = 0.025 × 0.5 = 0.0125
tf_mult = 1.0 (1H)
adjusted = 0.0125 × 1.0 = 0.0125
snapped = round(0.0125 / 0.005) × 0.005 = 0.015 (3 ticks)
```

**Step 2: Direction**
```
Strategy is trend, EMA(9) > EMA(21) → "long"
```

**Step 3: Levels (pyramid, long, 5 levels)**

| Level | Price | Lots |
|---|---|---|
| 1 | 95.500 | 7 |
| 2 | 95.485 | 11 |
| 3 | 95.470 | 18 |
| 4 | 95.455 | 25 |
| 5 | 95.440 | 37 |

**Step 4: Average entry**
```
avg = (95.500×7 + 95.485×11 + 95.470×18 + 95.455×25 + 95.440×37) / 98
avg = 95.4587
```

**Step 5: Stop and targets**
```
stop = 95.4587 - 0.025 × 1.5 = 95.4212
target_1 = 95.4587 + 0.025 × 2.0 = 95.5087
target_2 = 95.4587 + 0.025 × 4.0 = 95.5587
```

**Step 6: Risk/reward**
```
R:R = |95.5087 - 95.4587| / |95.4587 - 95.4212| = 0.050 / 0.0375 = 1.33
total_risk = (0.0375 / 0.005) × 20.835 × 98 = $15,313
```

---

## 14. Spread Ladder Considerations

For spread symbols:
- `tick_size` uses `spread_tick_size_bp` from product config
- `tick_value` uses `spread_tick_value`
- All prices are in basis points
- `entry_bp`, `avg_entry_bp`, `stop_bp`, `target_bp` fields are populated
- Direction is "steepener" or "flattener" instead of "long"/"short"
- ATR/DCW are computed from spread OHLCV (already in spread units)
