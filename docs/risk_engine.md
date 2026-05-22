# Risk Engine Documentation

> Tick math, basis-point math, position sizing, slippage, commissions, and risk/reward computation.

---

## 1. Overview

The risk engine (`app/services/risk_engine.py`) converts strategy signals and ladder outputs into concrete dollar-denominated risk assessments. It handles both outright contracts (price-quoted) and calendar spreads (basis-point-quoted).

---

## 2. Tick Math — Outrights

### Core Formula

```
distance_price = |entry - stop|
distance_ticks = distance_price / tick_size
risk_per_lot = distance_ticks × tick_value
total_risk = risk_per_lot × lots
```

### Fed Funds (ZQ) Example

| Parameter | Value |
|---|---|
| Entry | 95.500 |
| Stop | 95.465 |
| Tick size | 0.005 |
| Tick value | $20.835 |
| Lots | 10 |

```
distance = |95.500 - 95.465| = 0.035
ticks = 0.035 / 0.005 = 7 ticks
risk_per_lot = 7 × $20.835 = $145.85
total_risk = $145.85 × 10 = $1,458.45
```

### SOFR (SR3) Example

| Parameter | Value |
|---|---|
| Entry | 95.750 |
| Stop | 95.740 |
| Tick size | 0.0025 |
| Tick value | $6.25 |
| Lots | 50 |

```
distance = |95.750 - 95.740| = 0.010
ticks = 0.010 / 0.0025 = 4 ticks
risk_per_lot = 4 × $6.25 = $25.00
total_risk = $25.00 × 50 = $1,250.00
```

---

## 3. Basis-Point Math — Spreads

### Spread BP Convention

Calendar spreads are quoted in basis points:
```
spread_bp = (front_price - back_price) × 100
```

Where 1 full price point = 100 basis points.

### Spread Tick Size

For Fed Funds spreads:
- Tick size: 0.5 bp (`spread_tick_size_bp: 0.5`)
- Tick value: $20.835 (same dollar value as outright tick)

### Spread Risk Example

| Parameter | Value |
|---|---|
| Spread entry | -1.5 bp |
| Spread stop | -3.0 bp |
| Spread tick size | 0.5 bp |
| Spread tick value | $20.835 |
| Lots | 20 |

```
distance_bp = |-1.5 - (-3.0)| = 1.5 bp
ticks = 1.5 / 0.5 = 3 ticks
risk_per_lot = 3 × $20.835 = $62.51
total_risk = $62.51 × 20 = $1,250.10
```

---

## 4. Position Sizing

### From Account Risk

```
max_risk_usd = account_size × max_risk_per_trade_pct / 100
risk_per_lot = stop_ticks × tick_value
max_lots = floor(max_risk_usd / risk_per_lot)
```

### Default Account Parameters

| Parameter | Default | Source |
|---|---|---|
| `default_account_size` | $1,000,000 | `strategy_settings.yaml` |
| `max_risk_per_trade_pct` | 2.0% | `strategy_settings.yaml` |
| `max_risk_per_trade_usd` | $20,000 | `strategy_settings.yaml` |
| `max_position_lots` | 100 | `strategy_settings.yaml` |
| `max_open_risk_pct` | 10.0% | `strategy_settings.yaml` |

### Position Sizing Example

```
account = $1,000,000
max_risk = 2% = $20,000
stop_ticks = 7
tick_value = $20.835
risk_per_lot = 7 × $20.835 = $145.85
max_lots = floor($20,000 / $145.85) = 137 lots
cap = min(137, 100) = 100 lots  (max_position_lots limit)
```

---

## 5. Slippage Model

### Current Implementation

```
estimated_slippage_ticks = slippage_ticks (from config, default 1)
slippage_cost = slippage_ticks × tick_value × lots
```

### Usage in Risk

Slippage is added to the risk calculation:
```
effective_risk_ticks = stop_ticks + slippage_ticks
net_risk_per_lot = effective_risk_ticks × tick_value
```

### Configuration

```yaml
risk:
  slippage_ticks: 1
```

---

## 6. Commission Model

### Current Implementation

```
commission = lots × commission_per_lot × 2  (round trip)
```

### Configuration

```yaml
risk:
  commission_per_lot: 2.50
```

### Total Cost Example

```
lots = 100
commission_per_lot = $2.50
round_trip = 100 × $2.50 × 2 = $500.00
```

---

## 7. Total Risk Calculation

### Outright

```
gross_risk = stop_ticks × tick_value × lots
slippage = slippage_ticks × tick_value × lots
commissions = lots × commission × 2
total_risk = gross_risk + slippage + commissions
```

### Ladder Risk

The ladder engine computes risk from the weighted average entry:
```
stop_distance = |avg_entry - stop|
stop_ticks = stop_distance / tick_size
total_risk = stop_ticks × tick_value × total_lots
```

Note: Ladder risk uses the **average entry** not individual level entries. This means risk is measured from the complete position's blended entry to the stop.

---

## 8. Risk/Reward Ratio

```
reward_distance = |target_1 - avg_entry|
risk_distance = |avg_entry - stop|
R:R = reward_distance / risk_distance
```

### R:R by Strategy

| Strategy | Typical R:R | Explanation |
|---|---|---|
| Trend Fed Repricing | 1.33–2.67 | Wide targets in trending markets |
| Mean Reversion Range | 1.33–2.50 | Moderate targets, tight stops |
| Event Momentum | 1.25–2.50 | Extended targets, wide stops |
| Event Fade | 0.67–1.33 | Tight targets, moderate stops |
| Volatility Fade | 1.25–2.50 | Moderate targets, wide stops |

---

## 9. Volatility-Adjusted Sizing

The risk engine implicitly adjusts position size through ATR-based stops:

- Higher ATR → wider stop → fewer lots within max risk
- Lower ATR → tighter stop → more lots within max risk

This is a natural volatility-scaling mechanism. When volatility doubles, stop distance doubles, and max lots halve. This keeps dollar risk constant regardless of volatility level.

---

## 10. Risk Warnings

The platform generates warnings when:

| Condition | Warning |
|---|---|
| R:R < 1.0 | "Risk/reward ratio below 1.0 — unfavorable" |
| Total risk > max_risk_usd | "Risk exceeds maximum per-trade limit" |
| Vol percentile > 90 | "Extreme volatility — consider reducing size" |
| Vol percentile < 10 | "Very low volatility — may indicate illiquidity" |
| MTF alignment < 0.3 | "Poor multi-timeframe alignment" |
