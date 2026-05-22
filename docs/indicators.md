# Indicator Documentation

> Complete reference for all 30+ technical indicators: formulas, interpretation, strategy usage, timeframe impact, and ladder impact.

---

## 1. Overview

The indicator engine (`app/services/indicator_engine.py`) computes indicators across six categories. All computations use NumPy vectorized operations where possible. Indicators that require sequential state (EMA, ATR, RSI) use explicit loops with correct seeding.

**Configuration:** Indicator parameters (lengths, thresholds) are loaded from `strategy_settings.yaml` at engine initialization.

**Error handling:** Each indicator is wrapped in `_safe()` which catches `InsufficientDataError` (returns `None`) and logs unexpected errors without crashing the pipeline.

---

## 2. Trend Indicators

### 2.1 Simple Moving Average (SMA)

**Formula:**
```
SMA(n) = (1/n) × Σ(close[i]) for i = t-n+1 to t
```

**Default periods:** 20, 50 (configurable in YAML)

**Interpretation:**
- Price above SMA → bullish bias
- Price below SMA → bearish bias
- SMA(20) > SMA(50) → bullish crossover
- SMA(20) < SMA(50) → bearish crossover

**Strategy usage:** `MeanReversionRange` uses SMA(20) as the mean-reversion target. Deviation from SMA triggers reversion signals.

**Timeframe impact:** Longer timeframes produce smoother SMAs with less noise. SMA(20) on 1D = 20 trading days; on 1H = 20 hours.

**Ladder impact:** Not directly used for spacing, but SMA position influences direction inference.

---

### 2.2 Exponential Moving Average (EMA)

**Formula:**
```
multiplier = 2 / (n + 1)
EMA[0..n-1] = SMA(first n bars)    # Seed with SMA
EMA[i] = (close[i] - EMA[i-1]) × multiplier + EMA[i-1]
```

**Default periods:** 9, 21

**Interpretation:**
- EMA(9) > EMA(21) → short-term bullish alignment
- EMA(9) < EMA(21) → short-term bearish alignment
- EMA responds faster than SMA to recent price changes

**Strategy usage:** `TrendFedRepricing` checks EMA(9) vs EMA(21) alignment as the primary trend signal (+0.3 confidence).

**Ladder impact:** EMA alignment is one of three factors in the ladder engine's automatic direction inference. If EMA(9) > EMA(21), the engine infers LONG.

---

### 2.3 Hull Moving Average (HMA)

**Formula:**
```
half = floor(n / 2)
sqrt_n = floor(sqrt(n))
WMA_half = WMA(close, half)
WMA_full = WMA(close, n)
raw = 2 × WMA_half - WMA_full
HMA = WMA(raw, sqrt_n)
```

Where WMA (Weighted Moving Average):
```
WMA(data, n) = Σ(data[i] × weight[i]) / Σ(weight[i])
weights = [1, 2, 3, ..., n]
```

**Default periods:** 9, 16

**Interpretation:** HMA reduces lag compared to SMA/EMA of the same period while maintaining smoothness. It is particularly useful for identifying trend turns earlier.

**Strategy usage:** Available as an additional trend filter for future strategy enhancements. HMA crossover signals tend to lead EMA crossovers.

---

### 2.4 Kaufman Adaptive Moving Average (KAMA)

**Formula:**
```
ER = |close[i] - close[i-n]| / Σ|close[j] - close[j-1]| for j = i-n+1..i
fast_sc = 2 / (fast + 1)     # Default fast = 2
slow_sc = 2 / (slow + 1)     # Default slow = 30
SC = (ER × (fast_sc - slow_sc) + slow_sc)²
KAMA[i] = KAMA[i-1] + SC × (close[i] - KAMA[i-1])
```

Where ER = Efficiency Ratio (0 to 1). High ER = trending, Low ER = choppy.

**Default period:** 10

**Interpretation:** KAMA adapts its smoothing based on market efficiency. In trending markets (high ER), it tracks price closely. In choppy markets (low ER), it becomes very smooth, filtering noise.

**Strategy usage:** Confirms trend quality. A KAMA that tracks price closely indicates a clean trend suitable for trend-following strategies.

---

### 2.5 Volume Weighted Average Price (VWAP)

**Formula:**
```
TP[i] = (high[i] + low[i] + close[i]) / 3
VWAP[i] = Σ(TP[j] × volume[j]) / Σ(volume[j]) for j = 0..i
```

**Interpretation:** VWAP represents the average price weighted by volume, serving as a dynamic support/resistance level. Institutional traders use VWAP to assess execution quality.

- Price above VWAP → aggressive buying
- Price below VWAP → aggressive selling

**Strategy usage:** Provides context for entry optimization. Buying below VWAP in a long setup improves average entry quality.

---

### 2.6 Anchored VWAP

**Formula:** Same as VWAP but starting from a specific bar index (anchor point) rather than the first bar.

```
AVWAP[i] = Σ(TP[j] × volume[j]) / Σ(volume[j]) for j = anchor..i
```

**Default anchor:** Bar 0 (first bar in series)

**Interpretation:** Anchored VWAP from a significant event (FOMC decision, NFP release) shows the average price since that event. Institutional desks anchor VWAP to key macro events.

---

## 3. Volatility Indicators

### 3.1 Average True Range (ATR)

**Formula (Wilder smoothing):**
```
TR[i] = max(high[i] - low[i], |high[i] - close[i-1]|, |low[i] - close[i-1]|)
ATR[n] = mean(TR[1..n])          # Initial value
ATR[i] = (ATR[i-1] × (n-1) + TR[i]) / n   # Wilder smoothing
```

**Default period:** 14

**Interpretation:** ATR measures volatility in price units. Higher ATR = more volatile market. ATR expanding = trend acceleration. ATR contracting = range formation.

**Strategy usage:**
- `TrendFedRepricing` checks if recent ATR > 1.2× ATR from 5 bars ago (+0.2 confidence for ATR expansion)
- All strategies use ATR for stop/target placement: stop = entry ± ATR × multiplier

**Ladder impact:** **Critical.** ATR is the primary spacing source for trend and volatility regimes:
```
spacing_trend = ATR × 0.5 × timeframe_multiplier
spacing_volatility = ATR × 1.2 × timeframe_multiplier
```
ATR also determines stop distance (`ATR × stop_atr_mult`) and target distances.

---

### 3.2 Normalized ATR (NATR)

**Formula:**
```
NATR = (ATR / close) × 100
```

**Interpretation:** NATR expresses volatility as a percentage of price, making it comparable across different price levels and products.

**Usage:** Used internally for volatility percentile ranking in the ladder engine.

---

### 3.3 Historical Volatility (HV)

**Formula:**
```
log_return[i] = ln(close[i] / close[i-1])
HV = std(log_return[i-n..i], ddof=1) × √252 × 100
```

**Default period:** 20

**Interpretation:** Annualized standard deviation of log returns. HV of 15% means the instrument has historically moved about 15% per year (1 standard deviation).

**Usage:** Context indicator for risk assessment. Fed Funds futures typically have HV of 2–8%.

---

### 3.4 Realized Volatility (RV)

**Formula:**
```
log_return[i] = ln(close[i] / close[i-1])
RV = √(Σ(log_return²) × 252 / n) × 100
```

**Default period:** 20

**Interpretation:** Similar to HV but uses the sum of squared returns (no mean subtraction). RV is the standard measure used in variance swap pricing.

---

### 3.5 Bollinger Band Width (BBW)

**Formula:**
```
BBW = (upper_band - lower_band) / middle_band × 100
```

Where Bollinger Bands:
```
middle = SMA(close, n)
upper = middle + k × std(close, n)
lower = middle - k × std(close, n)
```

**Default:** n=20, k=2.0

**Interpretation:** BBW measures the width of Bollinger Bands as a percentage. Low BBW = Bollinger squeeze (compression, potential breakout). High BBW = extended move (potential exhaustion).

---

### 3.6 Donchian Channel Width (DCW)

**Formula:**
```
DCW = max(high[i-n+1..i]) - min(low[i-n+1..i])
```

**Default period:** 20

**Interpretation:** DCW measures the total price range over the lookback period. Narrow DCW = tight range (mean-reversion environment). Wide DCW = trending market.

**Ladder impact:** **Critical.** DCW is the primary spacing source for range regime:
```
spacing_range = DCW × 0.25 × timeframe_multiplier
```

---

### 3.7 Keltner Channels

**Formula:**
```
middle = EMA(close, n)
upper = middle + multiplier × ATR(n)
lower = middle - multiplier × ATR(n)
```

**Default:** n=20, multiplier=1.5

**Interpretation:** Keltner Channels combine trend (EMA) with volatility (ATR). Price outside Keltner Channels indicates a strong move. Bollinger Bands inside Keltner = squeeze setup.

---

## 4. Momentum Indicators

### 4.1 Relative Strength Index (RSI)

**Formula (Wilder smoothing):**
```
delta[i] = close[i] - close[i-1]
gain[i] = max(delta[i], 0)
loss[i] = max(-delta[i], 0)

avg_gain[n] = mean(gains[0..n-1])
avg_loss[n] = mean(losses[0..n-1])

avg_gain[i] = (avg_gain[i-1] × (n-1) + gain[i]) / n
avg_loss[i] = (avg_loss[i-1] × (n-1) + loss[i]) / n

RS = avg_gain / avg_loss
RSI = 100 - (100 / (1 + RS))
```

**Default period:** 14

**Interpretation:**
- RSI > 70 → overbought (potential reversal down)
- RSI < 30 → oversold (potential reversal up)
- RSI divergence from price → trend exhaustion signal

**Strategy usage:** Available for momentum strategies. RSI extremes confirm mean-reversion setups.

---

### 4.2 Stochastic RSI

**Formula:**
```
StochRSI_K = (RSI - min(RSI, stoch_len)) / (max(RSI, stoch_len) - min(RSI, stoch_len)) × 100
%K = SMA(StochRSI_K, k_smooth)
%D = SMA(%K, d_smooth)
```

**Default:** rsi_len=14, stoch_len=14, k_smooth=3, d_smooth=3

**Interpretation:** StochRSI is more sensitive than RSI alone. It oscillates between 0 and 100, with crossovers between %K and %D providing entry/exit signals.

---

### 4.3 MACD (Moving Average Convergence Divergence)

**Formula:**
```
MACD_line = EMA(close, fast) - EMA(close, slow)
Signal_line = EMA(MACD_line, signal)
Histogram = MACD_line - Signal_line
```

**Default:** fast=12, slow=26, signal=9

**Interpretation:**
- MACD > Signal → bullish momentum
- MACD < Signal → bearish momentum
- Histogram expanding → momentum accelerating
- Histogram contracting → momentum decelerating
- Zero-line crossover → trend change

---

### 4.4 Rate of Change (ROC)

**Formula:**
```
ROC = (close[i] - close[i-n]) / close[i-n] × 100
```

**Default period:** 14

**Interpretation:** Percentage price change over N bars. Positive ROC = upward momentum. Negative ROC = downward momentum.

---

### 4.5 Price Momentum

**Formula:**
```
Momentum = close[i] - close[i-n]
```

**Default period:** 14

**Interpretation:** Raw price difference (not percentage). Useful for spread analysis where absolute changes matter.

---

### 4.6 Percentage Price Oscillator (PPO)

**Formula:**
```
PPO = (EMA(fast) - EMA(slow)) / EMA(slow) × 100
```

**Default:** fast=12, slow=26

**Interpretation:** Like MACD but normalized as a percentage, making it comparable across different price levels.

---

## 5. Structure Indicators

### 5.1 Donchian Channels

**Formula:**
```
upper = max(high[i-n+1..i])
lower = min(low[i-n+1..i])
middle = (upper + lower) / 2
```

**Default period:** 20

**Strategy usage:** `TrendFedRepricing` checks if price is at the Donchian upper (breakout, +0.2 confidence for LONG) or Donchian lower (breakdown, +0.2 confidence for SHORT).

---

### 5.2 Bollinger Bands

**Formula:**
```
middle = SMA(close, n)
upper = middle + k × σ(close, n)
lower = middle - k × σ(close, n)
```

Where σ is the population standard deviation (ddof=0).

**Default:** n=20, k=2.0

**Strategy usage:** `MeanReversionRange` uses Bollinger position as the primary signal:
- Position > 0.95 → SHORT signal (+0.4 confidence, overbought)
- Position < 0.05 → LONG signal (+0.4 confidence, oversold)
- Position > 0.80 → SHORT signal (+0.25 confidence)
- Position < 0.20 → LONG signal (+0.25 confidence)

**Ladder impact:** Bollinger position is one of three factors in the ladder engine's direction inference. If price is in the upper 30% of Bollinger Bands, the engine infers SHORT.

---

### 5.3 Range Compression

**Formula:**
```
RC = current_DCW / avg_DCW(n)
```

**Interpretation:** RC < 1.0 = current range is compressed relative to average (range environment). RC > 1.0 = expanded range (trending or breakout).

**Strategy usage:** `MeanReversionRange` checks if DCW is compressed (recent_dcw / avg_dcw < 0.7, +0.2 confidence).

---

### 5.4 Expansion Detection

**Formula:**
```
Expansion = 1.0 if current_ATR > 1.5 × avg_ATR(n), else 0.0
```

**Interpretation:** Binary flag indicating volatility expansion. Used to confirm trend breakouts and avoid mean-reversion entries during expansion.

---

### 5.5 Session Range

**Formula:**
```
SessionRange[i] = high[i] - low[i]
```

**Interpretation:** Per-bar range as a measure of intraday volatility. Useful for identifying days with unusually wide or narrow ranges.

---

## 6. Spread Indicators

These indicators are **only computed for spread symbols** (detected by `-` in the symbol name). They analyze the behavior of calendar spreads.

### 6.1 Spread Z-Score

**Formula:**
```
Z = (spread[i] - SMA(spread, n)) / σ(spread, n)
```

Where σ uses ddof=1 (sample standard deviation).

**Default period:** 20

**Interpretation:** Z > +2 = spread is extended above mean (potential fade). Z < -2 = spread is extended below mean. Z near 0 = at fair value.

**Strategy usage:** Curve strategies use Z-score to identify extended spreads for mean-reversion trades.

---

### 6.2 Spread Mean Deviation

**Formula:**
```
MeanDev = spread[i] - SMA(spread, n)
```

**Interpretation:** Raw deviation from rolling mean in price units (not standardized).

---

### 6.3 Spread Velocity

**Formula:**
```
Velocity = spread[i] - spread[i-n]
```

**Default period:** 5

**Interpretation:** Rate of change of the spread over a short window. Positive velocity = spread widening. Negative velocity = spread narrowing.

---

### 6.4 Spread Acceleration

**Formula:**
```
Acceleration = velocity[i] - velocity[i-1]
```

**Interpretation:** Rate of change of velocity. Positive acceleration = spread move accelerating. Used to detect momentum shifts in spread behavior.

---

### 6.5 Curve Slope

**Formula:**
```
Slope = linear regression slope of spread over window of n bars
Slope = polyfit(x, spread[i-n+1..i], 1)[0]
```

**Default period:** 10

**Interpretation:** The trend direction of the spread. Positive slope = steepening trend. Negative slope = flattening trend.

---

### 6.6 Curve Momentum

**Formula:**
```
CurveMomentum = slope[i] - slope[i-1]
```

**Interpretation:** Acceleration of the spread's trend. Positive momentum with positive slope = steepening accelerating.

---

## 7. Liquidity Indicators

### 7.1 Relative Volume

**Formula:**
```
RelVol = volume[i] / SMA(volume, n)
```

**Default period:** 20

**Interpretation:** RelVol > 1.0 = above-average volume (institutional participation). RelVol > 2.0 = significant volume spike (event-driven). RelVol < 0.5 = thin market.

---

### 7.2 Volume Delta

**Formula:**
```
VolDelta = volume × sign(close - open)
```

**Interpretation:** Proxy for buying vs selling pressure. Positive delta = close above open (buying pressure). Negative delta = close below open (selling pressure). This is a simplified proxy for actual order flow delta.

---

## 8. Computation Pipeline

```
OHLCVSeries
  │
  ├── closes() → numpy array → SMA, EMA, HMA, KAMA, RSI, MACD, Bollinger, etc.
  ├── highs() → numpy array → Donchian upper, ATR true range
  ├── lows() → numpy array → Donchian lower, ATR true range
  ├── volumes() → numpy array → VWAP, RelVol, VolDelta
  │
  ▼
IndicatorSet (all results)
  │
  ▼
CacheManager.set_indicators(symbol, timeframe, indicator_set)
```

All indicators are computed in a single `compute_all()` call. Failed indicators (due to insufficient bars) are set to `None` without blocking other computations.
