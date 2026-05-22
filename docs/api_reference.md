# API Reference

> Complete REST API documentation with request/response schemas, validation, and examples.

---

## 1. Base URL

```
http://localhost:8000
```

Interactive documentation:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

---

## 2. Health Check

### GET /health

Returns application health status.

**Response:**
```json
{
  "status": "healthy",
  "app": "StrategyPlanner",
  "env": "development"
}
```

---

## 3. Market Data Endpoints

### POST /market-data/fetch

Fetch OHLCV data from external API and cache.

**Request:**
```json
{
  "product_key": "fed_funds",
  "symbols": ["FFN26", "FFQ26", "FFN26-FFQ26"],
  "timeframe": "1H"
}
```

| Field | Type | Required | Validation |
|---|---|---|---|
| `product_key` | string | Yes | Must exist in `contracts.yaml` |
| `symbols` | array[string] | Yes | Must be in product's contracts or spreads list |
| `timeframe` | string | Yes | Must be in supported_timeframes |

**Response (200):**
```json
{
  "success": true,
  "symbols_loaded": ["FFN26", "FFQ26", "FFN26-FFQ26"],
  "bars_per_symbol": {"FFN26": 500, "FFQ26": 500},
  "snapshots": [...],
  "spread_quotes": [...],
  "errors": []
}
```

**Error Responses:**
- 404: Contract/spread not found in config
- 502: External API error
- 500: Unexpected error

---

### POST /market-data/ingest

Fetch OHLCV and optionally compute indicators.

**Request:**
```json
{
  "product_key": "fed_funds",
  "symbols": ["FFN26"],
  "timeframe": "1H",
  "compute_indicators": true
}
```

Same as `/fetch` with additional field:

| Field | Type | Required | Default |
|---|---|---|---|
| `compute_indicators` | boolean | No | false |

**Response:** Same as `/fetch`, with indicator errors appended to `errors[]` if any.

---

### GET /market-data/snapshots

Returns all cached market snapshots and spread quotes.

**Response (200):**
```json
{
  "snapshots": {
    "FFN26": {
      "symbol": "FFN26",
      "last_price": 95.500,
      "volume": 12500.0,
      "high": 95.520,
      "low": 95.475,
      "change": 0.010,
      "change_pct": 0.01,
      "updated_at": "2026-01-15T14:30:00Z"
    }
  },
  "spreads": {
    "FFN26-FFQ26": {
      "spread_symbol": "FFN26-FFQ26",
      "front_leg": "FFN26",
      "back_leg": "FFQ26",
      "front_price": 95.500,
      "back_price": 95.515,
      "spread_bp": -1.5,
      "product_key": "fed_funds"
    }
  }
}
```

---

### GET /market-data/ohlcv/{symbol}/{timeframe}

Returns cached OHLCV bars.

**Path Parameters:**

| Parameter | Type | Example |
|---|---|---|
| `symbol` | string | FFN26 |
| `timeframe` | string | 1H |

**Response (200):**
```json
{
  "symbol": "FFN26",
  "timeframe": "1H",
  "bars": [
    {
      "timestamp": "2026-01-15T00:00:00",
      "open": 95.490,
      "high": 95.510,
      "low": 95.485,
      "close": 95.500,
      "volume": 250.0
    }
  ],
  "count": 500
}
```

**Error:** 404 if no cached data.

---

### GET /market-data/indicators/{symbol}/{timeframe}

Returns cached indicator set.

**Response (200):** Full `IndicatorSet` model dump (see contracts documentation).

**Error:** 404 if no cached indicators.

---

## 4. Strategy Endpoints

### POST /strategy/evaluate

Evaluate strategies for given symbols.

**Request:**
```json
{
  "product_key": "fed_funds",
  "symbols": ["FFN26", "FFQ26"],
  "timeframe": "1H",
  "strategies": null,
  "regime_override": null
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `product_key` | string | Yes | Product identifier |
| `symbols` | array[string] | Yes | Symbols to evaluate |
| `timeframe` | string | Yes | Timeframe |
| `strategies` | array[string] or null | No | Filter to specific strategies (null = all) |
| `regime_override` | string or null | No | Override cached regime for this evaluation |

**Response (200):**
```json
{
  "results": [
    {
      "symbol": "FFN26",
      "signals": [
        {
          "strategy_name": "trend_fed_repricing",
          "direction": "long",
          "strength": "moderate",
          "confidence": 0.65,
          "entry_price": 95.500,
          "stop_price": 95.450,
          "target_price": 95.575,
          "risk_reward_ratio": 1.50,
          "rationale": "EMA9 > EMA21 — bullish alignment | ATR expanding — trend acceleration",
          "regime": "trend",
          "macro_bias": "dovish"
        }
      ],
      "plans": [...]
    }
  ]
}
```

---

### GET /strategy/signals

Returns cached signal cards from the most recent evaluation.

---

### GET /strategy/risk/{symbol}

Returns risk assessment for a specific symbol.

---

## 5. Regime Endpoints

### PUT /regime/update

Set the current regime and macro bias.

**Request:**
```json
{
  "regime": "trend",
  "macro_bias": "dovish",
  "notes": "Post-FOMC repricing, market pricing in 50bp cut"
}
```

| Field | Type | Required | Options |
|---|---|---|---|
| `regime` | string | Yes | `trend`, `range`, `volatility`, `event` |
| `macro_bias` | string | Yes | `hawkish`, `dovish`, `neutral` |
| `notes` | string | No | Free-text notes |

**Response (200):**
```json
{
  "regime": "trend",
  "macro_bias": "dovish",
  "notes": "Post-FOMC repricing, market pricing in 50bp cut",
  "updated_at": "2026-01-15T14:30:00Z"
}
```

---

### GET /regime/current

Returns the current regime state.

**Response (200):**
```json
{
  "regime": "trend",
  "macro_bias": "dovish",
  "notes": "Post-FOMC repricing",
  "updated_at": "2026-01-15T14:30:00Z"
}
```

---

### GET /regime/suggest/{symbol}/{timeframe}

Returns a non-binding regime suggestion based on indicators.

**Response (200):**
```json
{
  "suggested_regime": "trend",
  "confidence": 0.70,
  "indicators": {
    "atr_expanding": true,
    "ema_aligned": true,
    "dcw_compressed": false
  }
}
```

---

## 6. Ladder Endpoints

### POST /ladder/generate

Generate an adaptive strategy ladder.

**Request:**
```json
{
  "product_key": "fed_funds",
  "symbol": "FFN26",
  "timeframe": "1H",
  "strategy": "trend_fed_repricing",
  "direction": null,
  "max_levels": 5,
  "lot_profile": null,
  "max_lots": null,
  "max_risk_usd": null
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `product_key` | string | Yes | Product identifier |
| `symbol` | string | Yes | Contract or spread symbol |
| `timeframe` | string | Yes | Timeframe |
| `strategy` | string | Yes | Strategy name |
| `direction` | string or null | No | "long", "short", "steepener", "flattener" (auto-inferred if null) |
| `max_levels` | int | No | Override max ladder levels (default: 5) |
| `lot_profile` | string or null | No | "pyramid", "equal", "front_loaded", "back_loaded" |
| `max_lots` | int or null | No | Override max position lots |
| `max_risk_usd` | float or null | No | Override max risk in USD |

**Response (200):**
```json
{
  "success": true,
  "ladder": {
    "strategy": "trend_fed_repricing",
    "symbol": "FFN26",
    "direction": "long",
    "regime": "trend",
    "levels": [
      {"level": 1, "entry_price": 95.500, "lots": 7, "cumulative_lots": 7},
      {"level": 2, "entry_price": 95.485, "lots": 11, "cumulative_lots": 18},
      {"level": 3, "entry_price": 95.470, "lots": 18, "cumulative_lots": 36},
      {"level": 4, "entry_price": 95.455, "lots": 25, "cumulative_lots": 61},
      {"level": 5, "entry_price": 95.440, "lots": 37, "cumulative_lots": 98}
    ],
    "avg_entry": 95.4587,
    "total_lots": 98,
    "stop": 95.4212,
    "target_1": 95.5087,
    "target_2": 95.5587,
    "risk_reward": 1.33,
    "total_risk_usd": 15313.0,
    "spacing_value": 0.015,
    "confidence": 0.75,
    "vol_percentile": 55.0,
    "mtf_alignment": 0.67
  },
  "error": null
}
```

**Error Response (422 or 500):**
```json
{
  "success": false,
  "ladder": null,
  "error": "No OHLCV data for FFN26:1H"
}
```

---

### GET /ladder/strategies

List all available strategies with their configuration.

**Response (200):**
```json
{
  "strategies": [
    {
      "name": "trend_fed_repricing",
      "enabled": true,
      "priority": 1,
      "applicable_regimes": ["trend"],
      "applicable_timeframes": ["1H", "4H", "1D"],
      "spread_only": false
    },
    ...
  ]
}
```

---

### GET /ladder/mtf/{symbol}/{timeframe}

Run multi-timeframe analysis.

**Path Parameters:**

| Parameter | Type | Example |
|---|---|---|
| `symbol` | string | FFN26 |
| `timeframe` | string | 1H |

**Response (200):**
```json
{
  "success": true,
  "analysis": {
    "symbol": "FFN26",
    "anchor_tf": "1H",
    "trend_alignment": 0.75,
    "volatility_alignment": 0.60,
    "structure_alignment": 0.50,
    "composite_score": 0.66,
    "direction_bias": "long",
    "timeframe_scores": {
      "1M": {"weight": 0.05, "trend": 0.0, "vol": 0.0, "structure": 0.0},
      "5M": {"weight": 0.10, "trend": 0.5, "vol": 0.3, "structure": 0.2},
      "15M": {"weight": 0.15, "trend": 0.7, "vol": 0.5, "structure": 0.4},
      "1H": {"weight": 0.25, "trend": 0.8, "vol": 0.6, "structure": 0.5},
      "4H": {"weight": 0.25, "trend": 0.9, "vol": 0.7, "structure": 0.6},
      "1D": {"weight": 0.20, "trend": 1.0, "vol": 0.8, "structure": 0.7}
    },
    "warnings": []
  },
  "adjustments": {
    "spacing": 1.05,
    "confidence": 0.08,
    "size": 0.85
  }
}
```

---

## 7. Account Endpoints

### GET /account/config

Returns current account configuration.

### PUT /account/config

Updates account configuration (risk limits, sizing parameters).

---

## 8. Page Routes

| Method | Path | Template | Description |
|---|---|---|---|
| GET | `/` | `dashboard/index.html` | Main dashboard |
| GET | `/strategy` | `strategy/index.html` | Strategy planner |
| GET | `/risk` | `risk/index.html` | Risk manager |
| GET | `/ladder` | `ladder/index.html` | Ladder planner |
| GET | `/replay` | `replay/index.html` | Replay engine |

Page routes return HTML (Jinja2-rendered). They load data from cache and pass it as template context.
