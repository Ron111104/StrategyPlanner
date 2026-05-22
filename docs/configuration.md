# Configuration Documentation

> Complete reference for all configuration files, environment variables, and extensibility patterns.

---

## 1. Configuration Architecture

The platform uses three configuration sources, loaded in this priority order:

1. **Environment variables / `.env` file** → `app/core/settings.py` (Pydantic Settings)
2. **`app/config/contracts.yaml`** → Product definitions, contracts, spreads, tick sizes
3. **`app/config/strategy_settings.yaml`** → Indicator parameters, strategy enablement, risk settings, ladder config

All YAML config is loaded via `app/config/loader.py` with `@lru_cache` — parsed exactly once per process lifetime unless explicitly reloaded.

---

## 2. Environment Variables (.env)

**File:** `.env` (loaded by `pydantic-settings`)
**Template:** `.env.example`

### Application Settings

| Variable | Type | Default | Description |
|---|---|---|---|
| `APP_NAME` | str | `StrategyPlanner` | Display name used in logs and UI |
| `APP_ENV` | enum | `development` | One of: `development`, `staging`, `production`. Controls debug behavior. |
| `APP_DEBUG` | bool | `true` | Enables uvicorn hot-reload and verbose error pages |
| `APP_HOST` | str | `0.0.0.0` | Network interface to bind |
| `APP_PORT` | int | `8000` | TCP port to listen on |

### External API Settings

| Variable | Type | Default | Description |
|---|---|---|---|
| `QH_API_BASE_URL` | str | `https://api.example.com` | Base URL for OHLCV data API. Must not have trailing slash. |
| `QH_API_KEY` | str | `""` | Bearer token sent in `Authorization` header. Leave empty if no auth required. |
| `QH_API_TIMEOUT` | int | `30` | HTTP request timeout in seconds for all API calls |

### Operational Settings

| Variable | Type | Default | Description |
|---|---|---|---|
| `LOG_LEVEL` | str | `INFO` | Python logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `LOG_FORMAT` | enum | `json` | `json` for structured logging (production), `console` for human-readable (development) |
| `CACHE_TTL_SECONDS` | int | `300` | Reserved for future TTL-based cache invalidation |
| `MAX_BARS_PER_REQUEST` | int | `5000` | Upper limit on OHLCV bars requested from external API |

### Derived Properties

The `Settings` class computes directory paths from `__file__`:

| Property | Value | Usage |
|---|---|---|
| `base_dir` | `app/` | Root of the application package |
| `config_dir` | `app/config/` | Location of YAML files |
| `templates_dir` | `app/templates/` | Jinja2 template root |
| `static_dir` | `app/static/` | Static file serving root |

---

## 3. contracts.yaml — Product Configuration

**File:** `app/config/contracts.yaml`
**Loader:** `load_contracts_config()` → `dict[str, Any]`

### Structure

```yaml
products:
  <product_key>:
    product_code: <str>          # CME product code (ZQ, SR3)
    display_name: <str>          # Human-readable name
    quote_format: <str>          # "price" (always)
    supported_timeframes:        # List of allowed timeframes
      - 1M
      - 5M
      - 15M
      - 1H
      - 4H
      - 1D
    outright_tick_size: <float>  # Minimum price increment for outrights
    outright_tick_value: <float> # Dollar value of one tick
    spread_tick_size_bp: <float> # Minimum BP increment for spreads
    spread_tick_value: <float>   # Dollar value of one spread tick
    contracts:                   # List of outright contract symbols
      - FFN26
      - FFQ26
    spreads:                     # List of calendar spread symbols
      - FFN26-FFQ26
```

### Current Products

#### Fed Funds (ZQ)

| Field | Value | Explanation |
|---|---|---|
| `product_code` | ZQ | CME product symbol |
| `outright_tick_size` | 0.005 | Half basis point (0.5 bp) |
| `outright_tick_value` | $20.835 | Dollar value per tick |
| `spread_tick_size_bp` | 0.5 | Half basis point |
| `spread_tick_value` | $20.835 | Same as outright tick value |
| `contracts` | FFN26 through FFH27 | 9 monthly contracts |
| `spreads` | FFN26-FFQ26 through FFG27-FFH27 | 8 calendar spreads |

#### SOFR (SR3)

| Field | Value | Explanation |
|---|---|---|
| `product_code` | SR3 | CME product symbol |
| `outright_tick_size` | 0.0025 | Quarter basis point (0.25 bp) |
| `outright_tick_value` | $6.25 | Dollar value per tick |
| `spread_tick_size_bp` | 0.25 | Quarter basis point |
| `spread_tick_value` | $6.25 | Same as outright tick value |
| `contracts` | SFRM26 through SFRH27 | 4 quarterly contracts |
| `spreads` | SFRM26-SFRU26 through SFRZ26-SFRH27 | 3 calendar spreads |

### How to Add a New Product

1. Add a new key under `products:` in `contracts.yaml`:

```yaml
products:
  eurodollar:
    product_code: GE
    display_name: Eurodollar Futures
    quote_format: price
    supported_timeframes: [1M, 5M, 15M, 1H, 4H, 1D]
    outright_tick_size: 0.0025
    outright_tick_value: 6.25
    spread_tick_size_bp: 0.25
    spread_tick_value: 6.25
    contracts:
      - GEM26
      - GEU26
    spreads:
      - GEM26-GEU26
```

2. No code changes required. The platform dynamically reads all products from config.

### How to Add a New Contract

Append the symbol to the `contracts` list:

```yaml
contracts:
  - FFN26
  - FFQ26
  - FFU26_NEW   # Add here
```

### How to Add a New Spread

Append the spread symbol (must be `FRONT-BACK` format) to the `spreads` list:

```yaml
spreads:
  - FFN26-FFQ26
  - FFU26_NEW-FFV26_NEW   # Add here
```

Both legs must exist in the `contracts` list.

---

## 4. strategy_settings.yaml — Strategy and Indicator Configuration

**File:** `app/config/strategy_settings.yaml`
**Loader:** `load_strategy_settings()` → `dict[str, Any]`

### Top-Level Structure

```yaml
indicators:
  <indicator_name>:
    <parameter>: <value>

strategies:
  <strategy_name>:
    enabled: <bool>
    priority: <int>
    applicable_regimes: [<regime>, ...]
    applicable_timeframes: [<tf>, ...]
    spread_only: <bool>

risk:
  <parameter>: <value>

event_windows:
  <parameter>: <value>

signal_thresholds:
  <parameter>: <value>

timeframes:
  allowed: [<tf>, ...]
  default_chart: <tf>
  default_indicator: <tf>
  default_strategy: <tf>

ladder:
  <parameter>: <value>

mtf:
  <parameter>: <value>
```

### Indicator Configuration

#### Moving Averages

```yaml
indicators:
  sma:
    default_lengths: [20, 50]    # Which SMA periods to compute
    min_length: 2
    max_length: 500
  ema:
    default_lengths: [9, 21]     # Which EMA periods to compute
    min_length: 2
    max_length: 500
  hma:
    default_lengths: [9, 16]
    min_length: 4
    max_length: 200
  kama:
    default_lengths: [10]
    fast_period: 2
    slow_period: 30
```

To change which SMA periods are computed, modify `default_lengths`. For example, to add SMA(200):

```yaml
sma:
  default_lengths: [20, 50, 200]
```

#### Volatility

```yaml
  atr:
    default_length: 14           # ATR lookback period
    min_length: 5
    max_length: 100
  bollinger:
    default_length: 20
    default_std_dev: 2.0
  dcw:
    default_length: 20
  keltner:
    default_length: 20
    default_multiplier: 1.5
```

#### Momentum

```yaml
  rsi:
    default_length: 14
    overbought: 70
    oversold: 30
  macd:
    fast: 12
    slow: 26
    signal: 9
  stoch_rsi:
    rsi_length: 14
    stoch_length: 14
    k_smooth: 3
    d_smooth: 3
```

### Strategy Configuration

Each strategy has:

| Field | Type | Description |
|---|---|---|
| `enabled` | bool | Whether the strategy is evaluated |
| `priority` | int | Evaluation order (1 = first) |
| `applicable_regimes` | list | Which regimes activate this strategy |
| `applicable_timeframes` | list | Which timeframes this strategy works on |
| `spread_only` | bool | If true, only evaluated for spread symbols |

Example:

```yaml
strategies:
  trend_fed_repricing:
    enabled: true
    priority: 1
    applicable_regimes: [trend]
    applicable_timeframes: [1H, 4H, 1D]
  curve_steepener:
    enabled: true
    priority: 6
    applicable_regimes: [trend, range]
    applicable_timeframes: [1H, 4H, 1D]
    spread_only: true
```

### Risk Configuration

```yaml
risk:
  default_account_size: 1000000
  max_risk_per_trade_pct: 2.0    # % of account
  max_risk_per_trade_usd: 20000
  max_position_lots: 100
  max_open_risk_pct: 10.0
  slippage_ticks: 1
  commission_per_lot: 2.50
  risk_free_rate: 0.0
```

### Ladder Configuration

```yaml
ladder:
  max_levels: 5                  # Maximum ladder levels
  default_lot_profile: pyramid   # Default distribution profile
  event_single_entry: true       # Single entry in event regime
  snap_to_tick_grid: true        # Round prices to tick increments
  spacing_regime:
    trend:
      source: ATR
      multiplier: 0.5
    range:
      source: DCW
      multiplier: 0.25
    volatility:
      source: ATR
      multiplier: 1.2
    event:
      source: NONE
      multiplier: 0.0
  timeframe_multipliers:
    1M: 0.3
    5M: 0.5
    15M: 0.7
    1H: 1.0
    4H: 1.5
    1D: 2.5
```

### MTF Configuration

```yaml
mtf:
  enabled: true
  composite_weights:
    trend: 0.50
    volatility: 0.25
    structure: 0.25
```

---

## 5. Configuration Loader

**File:** `app/config/loader.py`

### Functions

| Function | Cached | Description |
|---|---|---|
| `load_contracts_config()` | Yes (`@lru_cache`) | Returns full `contracts.yaml` as dict |
| `load_strategy_settings()` | Yes (`@lru_cache`) | Returns full `strategy_settings.yaml` as dict |
| `reload_contracts_config()` | Clears cache | For hot-reload scenarios |
| `reload_strategy_settings()` | Clears cache | For hot-reload scenarios |
| `get_product_config(key)` | Via parent cache | Returns single product dict, raises `ConfigurationError` if not found |
| `get_all_products()` | Via parent cache | Returns all products dict |
| `get_allowed_contracts(key)` | Via parent cache | Returns list of contract symbols |
| `get_allowed_spreads(key)` | Via parent cache | Returns list of spread symbols |

### Error Handling

- Missing YAML file → `ConfigurationError`
- Empty YAML file → `ConfigurationError`
- Invalid YAML syntax → `ConfigurationError`
- Unknown product key → `ConfigurationError` with available keys listed

---

## 6. How to Change Ladder Settings

To widen ladder spacing in trend regime:

```yaml
ladder:
  spacing_regime:
    trend:
      multiplier: 0.75  # was 0.5
```

To use 3 levels instead of 5:

```yaml
ladder:
  max_levels: 3
```

To change lot distribution to equal:

```yaml
ladder:
  default_lot_profile: equal  # was pyramid
```

---

## 7. How to Add a New Timeframe

1. Add to `strategy_settings.yaml`:

```yaml
timeframes:
  allowed:
    - 1M
    - 5M
    - 15M
    - 30M   # NEW
    - 1H
    - 4H
    - 1D
```

2. Add timeframe mapping in `app/adapters/qh_adapter.py`:

```python
TIMEFRAME_MAP["30M"] = "30min"
```

3. Add timeframe multiplier in ladder config:

```yaml
ladder:
  timeframe_multipliers:
    30M: 0.85
```

4. Add to product `supported_timeframes` in `contracts.yaml`.
