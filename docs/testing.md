# Testing Documentation

> Test suite architecture, fixtures, test categories, coverage, CI recommendations, and how to write new tests.

---

## 1. Overview

The platform has a comprehensive `pytest` test suite with **177 passing tests** covering all core modules. Tests live in `app/tests/` and are run via:

```bash
python -m pytest app/tests/ -v
```

### Dependencies

| Package | Version | Purpose |
|---|---|---|
| `pytest` | 8.3.4 | Test runner and assertion framework |
| `pytest-asyncio` | 0.25.0 | Async test support |
| `pytest-cov` | 6.0.0 | Coverage reporting |

---

## 2. Test Configuration

**File:** `app/tests/conftest.py`

### Key Fixtures

#### `reset_cache` (autouse, session-scoped)

Clears the `CacheManager` singleton before each test to prevent state leakage:

```python
@pytest.fixture(autouse=True)
def reset_cache():
    cache = CacheManager()
    cache.clear()
    yield
    cache.clear()
```

#### `sample_series`

Provides a realistic `OHLCVSeries` with 100 bars for indicator and strategy testing:

```python
@pytest.fixture
def sample_series():
    bars = []
    base_price = 95.500
    for i in range(100):
        noise = random.uniform(-0.03, 0.03)
        o = base_price + noise
        h = o + random.uniform(0.005, 0.02)
        l = o - random.uniform(0.005, 0.02)
        c = random.uniform(l, h)
        bars.append(OHLCVBar(
            timestamp=datetime(2026, 1, 1) + timedelta(hours=i),
            open=round(o, 4), high=round(h, 4),
            low=round(l, 4), close=round(c, 4),
            volume=random.uniform(100, 1000),
        ))
    return OHLCVSeries(symbol="FFN26", timeframe="1H", bars=bars, product_key="fed_funds")
```

#### `seeded_cache`

Pre-populates cache with OHLCV, indicators, and regime for ladder/MTF tests:

```python
@pytest.fixture
def seeded_cache(sample_series):
    cache = CacheManager()
    cache.set_ohlcv("FFN26", "1H", sample_series)
    engine = IndicatorEngine()
    indicators = engine.compute_all(sample_series)
    cache.set_indicators("FFN26", "1H", indicators)
    cache.set_regime(RegimeState(regime=RegimeType.TREND, macro_bias=MacroBias.DOVISH))
    return cache
```

---

## 3. Test Modules

### test_config.py — Configuration Tests

Tests YAML configuration loading and validation:
- `contracts.yaml` loads correctly
- `strategy_settings.yaml` loads correctly
- Product configuration contains required fields
- Unknown product key raises `ConfigurationError`
- Config caching works (same object returned)

### test_market_data.py — Market Data Tests

Tests OHLCV models and cache operations:
- `OHLCVBar` creation and validation
- `OHLCVSeries` utility methods (closes, highs, lows, volumes, latest, is_empty)
- Cache set/get/clear operations
- Multiple symbol-timeframe pairs cached independently

### test_spreads.py — Spread Tests

Tests spread computation and conventions:
- BP calculation: `(front - back) × 100`
- Positive and negative spreads
- SpreadQuote model validation
- Spread tick size and value from product config

### test_signals.py — Signal Model Tests

Tests signal and strategy signal models:
- Signal direction enum values
- Signal strength classification
- StrategySignal creation with all fields
- Confidence range validation (0.0–1.0)

### test_strategies.py — Strategy Tests

Tests all seven strategy implementations:
- Each strategy instantiation
- `evaluate()` with sample data and indicators
- Regime gating (correct regime returns signal, wrong regime returns None)
- `build_entry_exit_plan()` output structure
- Stop/target placement relative to entry
- Confidence scoring logic
- Direction determination

### test_new_indicators.py — Indicator Engine Tests

**31 tests** covering all expanded indicators:

| Test | Indicator | Assertions |
|---|---|---|
| `test_hma_computation` | HMA | Values not None, correct length |
| `test_kama_computation` | KAMA | Adapts to efficiency ratio |
| `test_vwap_computation` | VWAP | Monotonically close to price |
| `test_natr_computation` | NATR | Positive percentages |
| `test_historical_vol` | Historical Vol | Annualized, positive |
| `test_realized_vol` | Realized Vol | Positive |
| `test_bollinger_width` | BBW | Positive percentages |
| `test_keltner_channels` | Keltner | Upper > middle > lower |
| `test_rsi_computation` | RSI | Values between 0–100 |
| `test_stochrsi` | StochRSI | %K and %D between 0–100 |
| `test_macd` | MACD | Signal line and histogram exist |
| `test_roc` | ROC | Percentage values |
| `test_momentum` | Momentum | Price differences |
| `test_ppo` | PPO | Percentage oscillator |
| `test_range_compression` | Range Compression | Ratio values |
| `test_expansion_detection` | Expansion | Binary 0/1 flags |
| `test_session_range` | Session Range | Positive ranges |
| `test_spread_indicators` | All 8 spread indicators | Computed for spread symbols |
| `test_liquidity_indicators` | RelVol, VolDelta | Computed correctly |
| `test_compute_all` | Full pipeline | All categories populated |
| `test_insufficient_data` | Edge case | Graceful handling |

### test_ladder.py — Ladder Engine Tests

**22 tests** covering adaptive ladder generation:

| Test | Description |
|---|---|
| `test_basic_generation` | Ladder with 5 levels, correct structure |
| `test_event_regime_single` | Event regime produces single entry |
| `test_custom_max_levels` | max_levels parameter respected |
| `test_long_direction` | Long entries go below current price |
| `test_short_direction` | Short entries go above current price |
| `test_pyramid_profile` | Pyramid: more lots at deeper levels |
| `test_equal_profile` | Equal: same lots each level |
| `test_front_loaded` | More lots at first level |
| `test_stop_below_for_long` | Stop below avg_entry for long |
| `test_stop_above_for_short` | Stop above avg_entry for short |
| `test_target_above_for_long` | Target above avg_entry for long |
| `test_risk_reward_positive` | R:R > 0 |
| `test_spacing_tick_aligned` | Spacing is multiple of tick_size |
| `test_trend_spacing_uses_atr` | Trend regime uses ATR for spacing |
| `test_range_spacing_uses_dcw` | Range regime uses DCW for spacing |
| `test_vol_percentile` | Volatility percentile computed |
| `test_curve_steepener_direction` | Auto-inferred "steepener" |
| `test_curve_flattener_direction` | Auto-inferred "flattener" |
| `test_mtf_alignment` | MTF score computed |
| `test_confidence_range` | Confidence between 0–1 |
| `test_total_risk_positive` | Total risk > 0 |
| `test_avg_entry_between_levels` | Weighted average within range |

### test_mtf.py — Multi-Timeframe Engine Tests

**14 tests** covering MTF analysis:

| Test | Description |
|---|---|
| `test_analyze_returns_result` | Analysis produces output |
| `test_composite_score_range` | Score between -1 and +1 |
| `test_trend_alignment` | Trend scoring computed |
| `test_volatility_alignment` | Vol scoring computed |
| `test_structure_alignment` | Structure scoring computed |
| `test_direction_bias` | Direction inferred from scores |
| `test_adjustments_spacing` | Spacing adjustment factor |
| `test_adjustments_confidence` | Confidence adjustment |
| `test_adjustments_size` | Size adjustment |
| `test_single_timeframe` | Works with single TF data |
| `test_no_data` | Graceful fallback with no data |
| `test_all_aligned_bullish` | All TFs bullish → high score |
| `test_mixed_alignment` | Mixed TFs → moderate score |
| `test_weights_sum` | Composite weights sum to 1.0 |

### test_edge_cases.py — Edge Case Tests

Tests boundary conditions:
- Minimal bars (1–2 bars)
- Flat prices (all closes identical)
- Zero volume
- Empty series
- Very large bar counts

### test_latency.py — Performance Tests

Benchmarks computation latency:
- Indicator engine: compute_all for 500 bars < 100ms
- Ladder engine: generate < 50ms
- MTF engine: analyze < 100ms

### test_api.py — Integration Tests

Tests FastAPI endpoints using `TestClient`:
- Health check returns 200
- Market data endpoints accept correct request format
- Regime update returns updated state
- Strategy evaluate returns results structure
- Ladder generate returns AdaptiveLadder

---

## 4. Running Tests

### All Tests

```bash
python -m pytest app/tests/ -v
```

### Specific Module

```bash
python -m pytest app/tests/test_ladder.py -v
python -m pytest app/tests/test_new_indicators.py -v
```

### With Coverage

```bash
python -m pytest app/tests/ --cov=app --cov-report=html
# Open htmlcov/index.html in browser
```

### With Coverage (terminal)

```bash
python -m pytest app/tests/ --cov=app --cov-report=term-missing
```

### Parallel Execution

```bash
pip install pytest-xdist
python -m pytest app/tests/ -n auto
```

Note: Tests share a singleton cache, so parallel execution requires the `reset_cache` fixture to work correctly with xdist.

---

## 5. Writing New Tests

### Test File Naming

All test files must be named `test_*.py` and placed in `app/tests/`.

### Test Pattern

```python
import pytest
from app.services.my_engine import MyEngine
from app.contracts.my_model import MyModel

class TestMyEngine:
    def test_basic_computation(self, sample_series, seeded_cache):
        engine = MyEngine()
        result = engine.compute(sample_series)
        assert result is not None
        assert result.value > 0

    def test_edge_case(self, sample_series):
        engine = MyEngine()
        # Modify series to trigger edge case
        short_series = OHLCVSeries(
            symbol="FFN26", timeframe="1H",
            bars=sample_series.bars[:3], product_key="fed_funds"
        )
        result = engine.compute(short_series)
        assert result is None  # Graceful handling
```

### Async Tests

```python
import pytest

@pytest.mark.asyncio
async def test_async_fetch():
    adapter = QHAdapter(client=mock_client)
    result = await adapter.fetch_ohlcv("FFN26", "1H", "fed_funds")
    assert result is not None
```

---

## 6. CI Recommendations

### GitHub Actions Example

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: python -m pytest app/tests/ -v --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v3
        with:
          file: coverage.xml
```
