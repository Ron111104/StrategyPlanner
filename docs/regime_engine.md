# Regime Engine Documentation

> Market regime classification, macro bias overlay, strategy gating, and advisory system.

---

## 1. Overview

The regime engine (`app/services/regime_engine.py`) manages the current market regime and macro bias. The regime state is the **primary gate** that determines which strategies are evaluated and how ladders are generated.

In this platform, regime selection is **manual** — the trader explicitly chooses the regime based on their macro view. The engine provides an advisory suggestion, but the trader has final authority.

---

## 2. Regime Types

### Trend

**Definition:** The market is in a sustained directional move driven by macro repricing. Fed policy expectations are shifting, and prices are trending in one direction.

**Characteristics:**
- EMA(9) firmly above or below EMA(21)
- ATR expanding (accelerating move)
- Price at Donchian extremes
- Directional volume

**Activated strategies:** `trend_fed_repricing`, `curve_steepener`, `curve_flattener`

**Ladder behavior:** Spacing = ATR × 0.5 × TF multiplier (moderate spacing, follow the move)

**Typical duration:** Days to weeks around FOMC cycles

---

### Range

**Definition:** The market is consolidating between support and resistance levels. No clear directional catalyst. Price oscillates within a channel.

**Characteristics:**
- EMA(9) and EMA(21) intertwined
- DCW compressed
- Price mean-reverting within Bollinger Bands
- Bollinger Width contracting

**Activated strategies:** `mean_reversion_range`, `curve_steepener`, `curve_flattener`

**Ladder behavior:** Spacing = DCW × 0.25 × TF multiplier (tight spacing within the range)

**Typical duration:** Between FOMC meetings, during low-event periods

---

### Volatility

**Definition:** The market is experiencing elevated volatility without a clear directional trend. ATR is at extremes. Large intraday swings but no sustained direction.

**Characteristics:**
- ATR at 80th+ percentile
- Wide session ranges
- Bollinger Band expansion
- Volume spikes

**Activated strategies:** `volatility_fade`

**Ladder behavior:** Spacing = ATR × 1.2 × TF multiplier (wide spacing to survive volatility)

**Typical duration:** Event aftermath, options expiration, quarter-end

---

### Event

**Definition:** A specific macro event is imminent or just occurred (FOMC, NFP, CPI). The market is in a binary outcome state with extreme uncertainty.

**Characteristics:**
- Pre-event: low volume, compressed range, waiting
- Post-event: volume spike, ATR explosion, rapid repricing

**Activated strategies:** `event_momentum`, `event_fade`

**Ladder behavior:** **Single entry only** (`event_single_entry: true`) — no ladder, just one entry level with tight stop

**Typical duration:** Hours around event releases

---

## 3. Macro Bias

The macro bias overlays the regime with a Fed policy direction view:

### Hawkish

- Fed is expected to raise rates or delay cuts
- Dovish pricing will be unwound
- Supports SHORT direction for outrights (prices go down = rates go up)
- Supports flattening for spreads (front month rates rise faster)

### Dovish

- Fed is expected to cut rates or accelerate cuts
- Hawkish pricing will be unwound
- Supports LONG direction for outrights (prices go up = rates go down)
- Supports steepening for spreads (front month rates drop faster)

### Neutral

- No clear policy direction
- No directional bias applied
- Strategies operate purely on technical signals

### How Macro Bias Affects the Platform

| Component | Hawkish Effect | Dovish Effect | Neutral Effect |
|---|---|---|---|
| Strategy confidence | +0.15 if aligned with SHORT | +0.15 if aligned with LONG | No bonus |
| Ladder direction inference | Falls back to SHORT if no technical signal | Falls back to LONG | Falls back to LONG |
| Spread strategies | Favors flattener | Favors steepener | No preference |

---

## 4. RegimeState Model

```python
class RegimeState(BaseModel):
    regime: RegimeType = RegimeType.RANGE     # Default: range
    macro_bias: MacroBias = MacroBias.NEUTRAL  # Default: neutral
    notes: str = ""                            # Trader's notes
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

The regime state is stored in `CacheManager` and persists for the lifetime of the process (or until explicitly updated via `PUT /regime/update`).

---

## 5. Regime Advisory System

The advisory (`GET /regime/suggest/{symbol}/{tf}`) provides a non-binding suggestion:

### Advisory Logic

1. **Check ATR trend:** If ATR is expanding (recent > 1.3× average) → suggest "volatility" or "trend"
2. **Check EMA alignment:** If EMA(9) firmly above/below EMA(21) and ATR expanding → "trend"
3. **Check DCW compression:** If DCW < 0.7× average → "range"
4. **Check Bollinger Width:** If BBW contracting → "range"
5. **Default:** "range" (conservative)

### Advisory Response

```json
{
  "suggested_regime": "trend",
  "confidence": 0.7,
  "indicators": {
    "atr_expanding": true,
    "ema_aligned": true,
    "dcw_compressed": false
  },
  "notes": "ATR expanding with EMA alignment suggests trending market"
}
```

The trader may accept or ignore the suggestion.

---

## 6. Strategy Gating

When a strategy evaluation is requested, the engine checks:

```python
if current_regime not in strategy.applicable_regimes:
    return None  # Strategy skipped
```

### Gating Matrix

| Strategy | trend | range | volatility | event |
|---|---|---|---|---|
| trend_fed_repricing | ✅ | ❌ | ❌ | ❌ |
| mean_reversion_range | ❌ | ✅ | ❌ | ❌ |
| event_momentum | ❌ | ❌ | ❌ | ✅ |
| event_fade | ❌ | ❌ | ❌ | ✅ |
| volatility_fade | ❌ | ❌ | ✅ | ❌ |
| curve_steepener | ✅ | ✅ | ❌ | ❌ |
| curve_flattener | ✅ | ✅ | ❌ | ❌ |

---

## 7. Future: Automatic Regime Classification

The current manual regime selection will be enhanced with automatic classification in Phase 2:

- **Hidden Markov Model (HMM)** for regime state transition probabilities
- **ML classifier** trained on ATR, DCW, Bollinger Width, RSI, and volume features
- **Ensemble approach** combining technical and fundamental signals
- **Confidence scoring** with probability distribution across regime types
- **Override capability** — auto-classified regime is always overridable by the trader

The advisory system is the foundation for this future automatic classification.
