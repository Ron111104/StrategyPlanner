# Multi-Timeframe Engine Documentation

> Multi-timeframe alignment logic, scoring methodology, confirmation patterns, and ladder adaptation.

---

## 1. Overview

The Multi-Timeframe (MTF) Engine (`app/services/mtf_engine.py`) scores the alignment of market conditions across all supported timeframes (1M, 5M, 15M, 1H, 4H, 1D). The purpose is to confirm or weaken strategy signals and adjust ladder parameters based on whether higher and lower timeframes agree with the current timeframe's signal.

**File:** `app/services/mtf_engine.py`
**Class:** `MTFEngine`

---

## 2. Why Multi-Timeframe Analysis Matters

A LONG signal on the 1H chart has different conviction levels depending on what the 4H and 1D charts show:

| 1H Signal | 4H Trend | 1D Trend | Conviction |
|---|---|---|---|
| LONG | Bullish | Bullish | **High** — all timeframes aligned |
| LONG | Bullish | Bearish | **Moderate** — higher TF conflict |
| LONG | Bearish | Bearish | **Low** — signal contradicts higher TFs |

The MTF engine quantifies this alignment into a single composite score that the ladder engine uses to adjust spacing, confidence, and position sizing.

---

## 3. Timeframe Hierarchy

| Timeframe | Weight | Role |
|---|---|---|
| 1M | 0.05 | Scalping noise, minimal weight |
| 5M | 0.10 | Short-term micro-structure |
| 15M | 0.15 | Intraday structure |
| 1H | 0.25 | Primary trading timeframe |
| 4H | 0.25 | Swing context |
| 1D | 0.20 | Position/macro context |

Weights sum to 1.0 and are used to compute the weighted composite score.

---

## 4. Scoring Methodology

The MTF engine computes three sub-scores for each timeframe:

### 4.1 Trend Alignment

For each timeframe with cached indicators:

```python
ema_short = indicators.ema.get(9)
ema_long = indicators.ema.get(21)

if ema_short.values[-1] > ema_long.values[-1]:
    trend_score = +1.0  # Bullish
else:
    trend_score = -1.0  # Bearish
```

The trend score is +1 or -1 per timeframe.

### 4.2 Volatility Alignment

```python
atr_values = indicators.atr.values
current_atr = atr_values[-1]
avg_atr = mean(atr_values[-20:])
atr_ratio = current_atr / avg_atr

# Score:
# ratio > 1.5  → +1.0 (expanding, trend)
# ratio > 1.0  → +0.5 (mildly expanding)
# ratio < 0.7  → -0.5 (contracting, range)
# ratio < 0.5  → -1.0 (highly compressed)
```

### 4.3 Structure Alignment

```python
# Bollinger position
bb_pos = (close - lower) / (upper - lower)

# Score:
# bb_pos > 0.80 → +1.0 (near upper, bullish extension)
# bb_pos > 0.60 → +0.5 (mildly bullish)
# bb_pos < 0.20 → -1.0 (near lower, bearish extension)
# bb_pos < 0.40 → -0.5 (mildly bearish)
# else          →  0.0 (neutral)
```

---

## 5. Composite Score Calculation

For each timeframe `tf`:

```python
tf_score = (trend_weight × trend_score + vol_weight × vol_score + struct_weight × struct_score)
```

Default composite weights from `strategy_settings.yaml`:

```yaml
mtf:
  composite_weights:
    trend: 0.50
    volatility: 0.25
    structure: 0.25
```

The overall composite score is the weighted average across all timeframes:

```python
composite = Σ(tf_weight × tf_score) / Σ(tf_weight)  for all TFs with data
```

The composite score ranges from **-1.0** (all timeframes bearish) to **+1.0** (all timeframes bullish).

---

## 6. Direction Bias

The composite score determines the MTF direction bias:

| Composite Score | Bias |
|---|---|
| > +0.3 | Bullish |
| < -0.3 | Bearish |
| -0.3 to +0.3 | Neutral |

---

## 7. Adjustment Factors

The MTF engine produces three adjustment factors for the ladder engine:

### Spacing Adjustment

```python
# Strong alignment → tighter spacing (confident in direction)
# Weak alignment → wider spacing (more uncertainty)
if abs(composite) > 0.7:
    spacing_factor = 0.85  # Tighter
elif abs(composite) > 0.4:
    spacing_factor = 1.0   # Normal
else:
    spacing_factor = 1.15  # Wider
```

### Confidence Adjustment

```python
# Direct mapping from composite to confidence bonus
confidence_bonus = max(-0.15, min(0.15, composite * 0.2))
```

Range: -0.15 to +0.15 added to ladder confidence.

### Size Adjustment

```python
# Strong alignment → allow full position
# Weak alignment → reduce position
if abs(composite) > 0.7:
    size_factor = 1.0
elif abs(composite) > 0.4:
    size_factor = 0.85
else:
    size_factor = 0.70
```

---

## 8. Analysis Output

The `MTFEngine.analyze()` method returns a complete analysis result:

```python
{
    "symbol": "FFN26",
    "anchor_tf": "1H",
    "trend_alignment": 0.75,         # Aggregate trend score
    "volatility_alignment": 0.60,    # Aggregate vol score
    "structure_alignment": 0.50,     # Aggregate structure score
    "composite_score": 0.66,         # Weighted composite
    "direction_bias": "long",        # Derived from composite
    "timeframe_scores": {
        "1M": {"weight": 0.05, "trend": 0.0, "vol": 0.0, "structure": 0.0},
        "5M": {"weight": 0.10, "trend": 0.5, "vol": 0.3, "structure": 0.2},
        ...
    },
    "adjustments": {
        "spacing": 0.85,     # Multiply ladder spacing by this
        "confidence": 0.08,  # Add to ladder confidence
        "size": 1.0          # Multiply lot count by this
    },
    "warnings": []
}
```

---

## 9. Integration with Ladder Engine

The ladder engine calls `_compute_mtf_alignment()` which:

1. Iterates over all timeframes **above** the current timeframe
2. Checks EMA(9) vs EMA(21) alignment with the trade direction
3. Returns a simplified alignment score (0.0 to 1.0)

The full MTF analysis is available via the `/ladder/mtf/{symbol}/{timeframe}` endpoint for detailed inspection.

---

## 10. Data Requirements

The MTF engine requires cached indicators for each timeframe it analyzes. If indicators are not available for a timeframe, that timeframe is skipped and excluded from the weighted average.

**Best practice:** Ingest data for all timeframes before running MTF analysis:

```bash
# Ingest across all timeframes
POST /market-data/ingest {"product_key": "fed_funds", "symbols": ["FFN26"], "timeframe": "1M", "compute_indicators": true}
POST /market-data/ingest {"product_key": "fed_funds", "symbols": ["FFN26"], "timeframe": "5M", "compute_indicators": true}
POST /market-data/ingest {"product_key": "fed_funds", "symbols": ["FFN26"], "timeframe": "15M", "compute_indicators": true}
POST /market-data/ingest {"product_key": "fed_funds", "symbols": ["FFN26"], "timeframe": "1H", "compute_indicators": true}
POST /market-data/ingest {"product_key": "fed_funds", "symbols": ["FFN26"], "timeframe": "4H", "compute_indicators": true}
POST /market-data/ingest {"product_key": "fed_funds", "symbols": ["FFN26"], "timeframe": "1D", "compute_indicators": true}
```

With all timeframes ingested, the MTF engine produces the most accurate alignment scores.
