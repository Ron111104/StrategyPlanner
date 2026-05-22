# Contracts Documentation

> Complete reference for all Pydantic v2 data models, typing conventions, validation logic, and unit standards.

---

## 1. Overview

The contracts layer (`app/contracts/`) defines all typed data boundaries in the platform. Every piece of data flowing between services, routes, cache, and frontend is a Pydantic `BaseModel`. No raw dictionaries cross module boundaries except YAML config loaded as `dict[str, Any]`.

All models use:
- **Pydantic v2** (`pydantic>=2.10`)
- **Python 3.12+ type hints** (including `X | None` union syntax)
- **`Field()` with defaults and validators** for business constraints
- **Enums** for fixed-domain values (regime types, signal directions, timeframes)

---

## 2. Market Data Models

**File:** `app/contracts/market_data.py`

### OHLCVBar

A single candlestick bar.

| Field | Type | Unit | Validation |
|---|---|---|---|
| `timestamp` | `datetime` | UTC | Required |
| `open` | `float` | Price (outrights) or BP (spreads) | Required |
| `high` | `float` | Price or BP | Required |
| `low` | `float` | Price or BP | Required |
| `close` | `float` | Price or BP | Required |
| `volume` | `float` | Contracts | Default 0.0 |

**Note on units:** For outright contracts (e.g., FFN26), prices are in Fed Funds price format (e.g., 95.500 meaning an implied rate of 4.500%). For spread symbols constructed from legs, the close represents the differential in the same price units. Conversion to basis points happens at the `SpreadQuote` level.

### OHLCVSeries

A time-ordered collection of bars for one symbol and one timeframe.

| Field | Type | Description |
|---|---|---|
| `symbol` | `str` | Contract or spread symbol (e.g., `FFN26`, `FFN26-FFQ26`) |
| `timeframe` | `str` | Timeframe key (e.g., `1H`, `4H`) |
| `bars` | `list[OHLCVBar]` | Ordered list of bars (oldest first) |
| `product_key` | `str` | Product identifier (e.g., `fed_funds`) |

**Utility methods:**

| Method | Returns | Description |
|---|---|---|
| `closes()` | `list[float]` | All close prices |
| `highs()` | `list[float]` | All high prices |
| `lows()` | `list[float]` | All low prices |
| `opens()` | `list[float]` | All open prices |
| `volumes()` | `list[float]` | All volumes |
| `latest` | `OHLCVBar | None` | Last bar in series |
| `is_empty` | `bool` | True if no bars |
| `length` | `int` | Number of bars |

### MarketSnapshot

A point-in-time summary of a single contract.

| Field | Type | Description |
|---|---|---|
| `symbol` | `str` | Contract symbol |
| `last_price` | `float` | Most recent close |
| `bid` | `float | None` | Best bid (if available) |
| `ask` | `float | None` | Best ask (if available) |
| `volume` | `float` | Session volume |
| `high` | `float` | Session high |
| `low` | `float` | Session low |
| `change` | `float` | Price change |
| `change_pct` | `float` | Percentage change |
| `updated_at` | `datetime` | Snapshot timestamp |

### SpreadQuote

A computed calendar spread quote.

| Field | Type | Unit | Description |
|---|---|---|---|
| `spread_symbol` | `str` | — | e.g., `FFN26-FFQ26` |
| `front_leg` | `str` | — | Front contract symbol |
| `back_leg` | `str` | — | Back contract symbol |
| `front_price` | `float` | Price | Front contract close |
| `back_price` | `float` | Price | Back contract close |
| `spread_bp` | `float` | **Basis points** | `(front - back) × 100` |
| `product_key` | `str` | — | Product identifier |

**BP Conversion:**
```
spread_bp = (front_price - back_price) × 100
```

Example: If FFN26 = 95.500 and FFQ26 = 95.515, then:
```
spread_bp = (95.500 - 95.515) × 100 = -1.5 bp
```

This means the front month is 1.5 basis points lower than the back month (normal backwardation for Fed Funds when rates are expected to fall).

---

## 3. Product Models

**File:** `app/contracts/products.py`

### TimeframeEnum

```python
class TimeframeEnum(str, Enum):
    M1 = "1M"
    M5 = "5M"
    M15 = "15M"
    H1 = "1H"
    H4 = "4H"
    D1 = "1D"
```

### ProductConfig

Validated product configuration loaded from YAML.

| Field | Type | Description |
|---|---|---|
| `product_key` | `str` | Internal key (e.g., `fed_funds`) |
| `product_code` | `str` | CME code (e.g., `ZQ`) |
| `display_name` | `str` | Human-readable name |
| `quote_format` | `str` | Always `"price"` |
| `supported_timeframes` | `list[str]` | Allowed timeframes |
| `outright_tick_size` | `float` | Minimum price increment |
| `outright_tick_value` | `float` | Dollar value per tick |
| `spread_tick_size_bp` | `float` | Minimum BP increment for spreads |
| `spread_tick_value` | `float` | Dollar value per spread tick |
| `contracts` | `list[str]` | Outright contract symbols |
| `spreads` | `list[str]` | Calendar spread symbols |

### ProductSummary

Lightweight summary for API responses.

| Field | Type | Description |
|---|---|---|
| `product_key` | `str` | Internal key |
| `product_code` | `str` | CME code |
| `display_name` | `str` | Name |
| `num_contracts` | `int` | Count of outrights |
| `num_spreads` | `int` | Count of spreads |
| `supported_timeframes` | `list[str]` | Allowed timeframes |

---

## 4. Indicator Models

**File:** `app/contracts/indicators.py`

### IndicatorResult

A single computed indicator result.

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Indicator identifier (e.g., `SMA_20`, `ATR`, `MACD`) |
| `symbol` | `str` | Contract/spread symbol |
| `timeframe` | `str` | Timeframe |
| `values` | `list[float]` | Computed values (aligned with timestamps) |
| `timestamps` | `list[datetime]` | Corresponding bar timestamps |
| `params` | `dict[str, float]` | Parameters used (e.g., `{"length": 20.0}`) |
| `upper_band` | `list[float] | None` | Upper band (Bollinger, Donchian, Keltner) |
| `lower_band` | `list[float] | None` | Lower band |
| `middle_band` | `list[float] | None` | Middle band |
| `signal_line` | `list[float] | None` | Signal line (MACD, StochRSI) |
| `histogram` | `list[float] | None` | Histogram (MACD) |

### IndicatorSet

Container for all indicators computed for a symbol/timeframe.

| Field | Type | Description |
|---|---|---|
| `symbol` | `str` | Symbol |
| `timeframe` | `str` | Timeframe |
| **Trend** | | |
| `sma` | `dict[int, IndicatorResult]` | SMA by period (e.g., `{20: ..., 50: ...}`) |
| `ema` | `dict[int, IndicatorResult]` | EMA by period |
| `hma` | `dict[int, IndicatorResult]` | HMA by period |
| `kama` | `dict[int, IndicatorResult]` | KAMA by period |
| `vwap` | `IndicatorResult | None` | VWAP |
| `anchored_vwap` | `IndicatorResult | None` | Anchored VWAP |
| **Volatility** | | |
| `atr` | `IndicatorResult | None` | ATR |
| `natr` | `IndicatorResult | None` | Normalized ATR |
| `historical_vol` | `IndicatorResult | None` | Historical Volatility |
| `realized_vol` | `IndicatorResult | None` | Realized Volatility |
| `bollinger_width` | `IndicatorResult | None` | Bollinger Band Width |
| `dcw` | `IndicatorResult | None` | Donchian Channel Width |
| `keltner` | `IndicatorResult | None` | Keltner Channels |
| **Momentum** | | |
| `rsi` | `IndicatorResult | None` | RSI |
| `stoch_rsi` | `IndicatorResult | None` | Stochastic RSI |
| `macd` | `IndicatorResult | None` | MACD |
| `roc` | `IndicatorResult | None` | Rate of Change |
| `momentum` | `IndicatorResult | None` | Price Momentum |
| `ppo` | `IndicatorResult | None` | Percentage Price Oscillator |
| **Structure** | | |
| `donchian` | `IndicatorResult | None` | Donchian Channels |
| `bollinger` | `IndicatorResult | None` | Bollinger Bands |
| `range_compression` | `IndicatorResult | None` | Range Compression |
| `expansion_detection` | `IndicatorResult | None` | Expansion Detection |
| `session_range` | `IndicatorResult | None` | Session Range |
| **Spread** | | |
| `spread_zscore` | `IndicatorResult | None` | Spread Z-score |
| `spread_mean_dev` | `IndicatorResult | None` | Spread Mean Deviation |
| `spread_velocity` | `IndicatorResult | None` | Spread Velocity |
| `spread_acceleration` | `IndicatorResult | None` | Spread Acceleration |
| `curve_slope` | `IndicatorResult | None` | Curve Slope |
| `curve_momentum` | `IndicatorResult | None` | Curve Momentum |
| `spread_atr` | `IndicatorResult | None` | Spread ATR |
| `spread_dcw` | `IndicatorResult | None` | Spread DCW |
| **Liquidity** | | |
| `relative_volume` | `IndicatorResult | None` | Relative Volume |
| `volume_delta` | `IndicatorResult | None` | Volume Delta |

---

## 5. Signal Models

**File:** `app/contracts/signals.py`

### SignalDirection

```python
class SignalDirection(str, Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"
```

### SignalStrength

```python
class SignalStrength(str, Enum):
    STRONG = "strong"      # confidence >= 0.7
    MODERATE = "moderate"  # 0.5 <= confidence < 0.7
    WEAK = "weak"          # confidence < 0.5
```

### StrategySignal

The output of a strategy evaluation.

| Field | Type | Description |
|---|---|---|
| `strategy_name` | `str` | Which strategy produced this signal |
| `symbol` | `str` | Contract/spread |
| `timeframe` | `str` | Timeframe evaluated |
| `direction` | `SignalDirection` | LONG, SHORT, or FLAT |
| `strength` | `SignalStrength` | STRONG, MODERATE, or WEAK |
| `confidence` | `float` | 0.0 to 1.0 |
| `entry_price` | `float | None` | Suggested entry |
| `stop_price` | `float | None` | Suggested stop |
| `target_price` | `float | None` | Primary target |
| `risk_reward_ratio` | `float | None` | R:R ratio |
| `rationale` | `str` | Human-readable reasoning |
| `regime` | `str` | Active regime when signal was generated |
| `macro_bias` | `str` | Active macro bias |

---

## 6. Strategy Models

**File:** `app/contracts/strategy.py`

### EntryExitPlan

A detailed trade plan produced by a strategy.

| Field | Type | Description |
|---|---|---|
| `symbol` | `str` | Contract/spread |
| `strategy_name` | `str` | Source strategy |
| `direction` | `str` | "long" or "short" |
| `entry_price` | `float` | Entry price |
| `stop_price` | `float` | Stop price |
| `primary_target` | `float` | Target 1 |
| `secondary_target` | `float | None` | Target 2 |
| `tertiary_target` | `float | None` | Target 3 |
| `risk_ticks` | `float` | Ticks at risk |
| `reward_ticks` | `float` | Ticks to target |
| `risk_reward_ratio` | `float` | R:R |
| `confidence` | `float` | Strategy confidence |
| `rationale` | `str` | Explanation |

---

## 7. Regime Models

**File:** `app/contracts/regime.py`

### RegimeType

```python
class RegimeType(str, Enum):
    TREND = "trend"
    RANGE = "range"
    VOLATILITY = "volatility"
    EVENT = "event"
```

### MacroBias

```python
class MacroBias(str, Enum):
    HAWKISH = "hawkish"
    DOVISH = "dovish"
    NEUTRAL = "neutral"
```

### RegimeState

| Field | Type | Default | Description |
|---|---|---|---|
| `regime` | `RegimeType` | `RANGE` | Current market regime |
| `macro_bias` | `MacroBias` | `NEUTRAL` | Fed policy bias |
| `notes` | `str` | `""` | Trader's notes |
| `updated_at` | `datetime` | `utcnow()` | Last update timestamp |

---

## 8. Ladder Models

**File:** `app/contracts/ladder.py`

### AdaptiveLadderLevel

A single level in the entry ladder.

| Field | Type | Unit | Description |
|---|---|---|---|
| `level` | `int` | — | Level number (1 = first entry) |
| `price` | `float` | Price or BP | Entry price for this level |
| `lots` | `int` | Contracts | Number of lots at this level |
| `cumulative_lots` | `int` | Contracts | Running total of lots |
| `distance_from_first` | `float` | Price or BP | Distance from level 1 |
| `risk_per_lot` | `float` | USD | Risk per lot to stop |

### AdaptiveLadder

The complete ladder output.

| Field | Type | Description |
|---|---|---|
| `symbol` | `str` | Contract/spread |
| `timeframe` | `str` | Timeframe |
| `strategy` | `str` | Strategy name |
| `direction` | `str` | "long" or "short" |
| `regime` | `str` | Active regime |
| `macro_bias` | `str` | Active macro bias |
| `levels` | `list[AdaptiveLadderLevel]` | Entry levels |
| `avg_entry` | `float` | Weighted average entry |
| `total_lots` | `int` | Sum of all lots |
| `stop_price` | `float` | Stop price |
| `target_1` | `float` | Primary target |
| `target_2` | `float` | Secondary target |
| `risk_reward` | `float` | R:R ratio |
| `total_risk_usd` | `float` | Total dollar risk |
| `spacing` | `float` | Spacing between levels |
| `lot_profile` | `str` | Distribution profile used |
| `atr_value` | `float` | Current ATR |
| `dcw_value` | `float` | Current DCW |
| `vol_percentile` | `float` | Volatility percentile (0–100) |
| `mtf_alignment` | `float` | MTF score (-1 to +1) |
| `confidence` | `float` | Overall confidence (0–1) |
| `notes` | `str` | Context notes |

### LadderRequest

API request body for ladder generation.

| Field | Type | Required | Description |
|---|---|---|---|
| `product_key` | `str` | Yes | Product identifier |
| `symbol` | `str` | Yes | Contract/spread symbol |
| `timeframe` | `str` | Yes | Timeframe |
| `strategy` | `str` | Yes | Strategy name |
| `direction` | `str | None` | No | Override direction (auto-inferred if omitted) |
| `max_levels` | `int | None` | No | Override max levels (default from config) |
| `lot_profile` | `str | None` | No | Override lot profile (default from config) |

### LadderResponse

API response wrapper.

| Field | Type | Description |
|---|---|---|
| `success` | `bool` | Whether generation succeeded |
| `ladder` | `AdaptiveLadder | None` | The generated ladder |
| `error` | `str | None` | Error message if failed |

---

## 9. Unit Conventions

### Outright Prices

- **Format:** Decimal price (e.g., `95.500`)
- **Meaning:** `100 - implied_rate`. A price of 95.500 implies a rate of 4.500%.
- **Tick size:** 0.005 (Fed Funds) or 0.0025 (SOFR)
- **Tick value:** $20.835 (Fed Funds) or $6.25 (SOFR)

### Spread Basis Points

- **Format:** Decimal BP (e.g., `-1.5`)
- **Meaning:** `(front_price - back_price) × 100`
- **Tick size:** 0.5 bp (Fed Funds) or 0.25 bp (SOFR)
- **Tick value:** Same as outright tick value
- **Convention:** Negative spread = front month priced below back month (rates expected to fall)

### Indicator Values

- **ATR, DCW:** In price units (same as the input OHLCV)
- **NATR:** Percentage (ATR / close × 100)
- **Historical Vol, Realized Vol:** Annualized percentage (× √252 × 100)
- **RSI:** 0–100 scale
- **Stochastic RSI:** 0–100 scale
- **MACD:** Price units (EMA difference)
- **ROC:** Percentage change
- **Bollinger Width:** Percentage ((upper - lower) / middle × 100)
- **Z-score:** Standard deviations from mean (dimensionless)
- **Relative Volume:** Ratio (current / average, dimensionless)
