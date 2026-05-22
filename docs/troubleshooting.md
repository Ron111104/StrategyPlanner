# Troubleshooting Guide

> Common issues, error messages, root causes, and resolutions.

---

## 1. Application Won't Start

### Error: `ModuleNotFoundError: No module named 'app'`

**Cause:** Running from wrong directory or virtual environment not activated.

**Fix:**
```bash
cd StrategyPlanner          # Must be in project root
.venv\Scripts\activate      # Activate venv (Windows)
source .venv/bin/activate   # (Linux/macOS)
python run.py
```

### Error: `ModuleNotFoundError: No module named 'fastapi'`

**Cause:** Dependencies not installed.

**Fix:**
```bash
pip install -r requirements.txt
```

### Error: `SyntaxError: X | None` or `X | Y`

**Cause:** Python version < 3.10 (union type syntax requires 3.10+, some features require 3.12+).

**Fix:** Install Python 3.12+.

### Error: Port 8000 already in use

**Cause:** Another process is using port 8000.

**Fix:**
```bash
# Find the process (Windows)
netstat -ano | findstr :8000

# Find the process (Linux/macOS)
lsof -i :8000

# Kill it or change APP_PORT in .env
```

---

## 2. Market Data Issues

### Error: `MarketDataError: HTTP 401`

**Cause:** Missing or invalid API key.

**Fix:** Set `QH_API_KEY` in `.env` with a valid API key.

### Error: `MarketDataError: HTTP 404` when fetching data

**Cause:** Symbol not recognized by external API.

**Fix:**
- Verify the symbol exists in `contracts.yaml`
- Check that the external API supports this symbol
- Verify `QH_API_BASE_URL` is correct

### Error: `MarketDataError: Connection refused`

**Cause:** External API is unreachable.

**Fix:**
- Check `QH_API_BASE_URL` in `.env`
- Verify network connectivity
- Check if the API is behind a VPN

### Error: `Contract 'XYZ' not in allowed contracts for fed_funds`

**Cause:** Symbol not in the `contracts` list in `contracts.yaml`.

**Fix:** Add the symbol to the appropriate product's `contracts` list in `app/config/contracts.yaml`.

### Error: `Spread 'XYZ-ABC' not in allowed spreads`

**Cause:** Spread not configured.

**Fix:** Add the spread symbol to the `spreads` list and ensure both legs are in the `contracts` list.

### No data returned (empty bars)

**Cause:** External API returned empty response.

**Fix:**
- Check if the contract is expired (historical data may not be available)
- Try a different timeframe
- Check API rate limits

---

## 3. Indicator Issues

### Error: `InsufficientDataError: Need at least N bars`

**Cause:** Not enough OHLCV bars for the requested indicator period.

**Fix:**
- Fetch more historical data
- Reduce indicator periods in `strategy_settings.yaml`
- Use a shorter timeframe (more bars per time period)

### Indicators return None

**Cause:** Too few bars for the indicator's lookback period. For example, SMA(50) needs at least 50 bars.

**Fix:** Fetch at least 100+ bars. The indicator engine gracefully returns `None` for indicators that can't be computed.

### ATR or DCW is zero

**Cause:** All bars have identical OHLCV values (flat market, synthetic data).

**Fix:** This is expected for truly flat data. In live markets, this shouldn't happen.

---

## 4. Strategy Issues

### No strategies fire

**Cause:** One or more of:
- Wrong regime selected (strategies are regime-gated)
- Timeframe not in strategy's `applicable_timeframes`
- Confidence below minimum threshold
- No indicators available

**Fix:**
- Check `GET /regime/current` — is the regime correct for your expected strategy?
- Check `strategy_settings.yaml` for the strategy's `applicable_regimes` and `applicable_timeframes`
- Ensure indicators are computed (use `/market-data/ingest` with `compute_indicators: true`)

### Strategy fires with wrong direction

**Cause:** Macro bias or indicator alignment may conflict with expected direction.

**Fix:**
- Check macro bias — hawkish bias promotes SHORT
- Check EMA alignment — EMA(9) vs EMA(21) determines trend direction
- Strategies use multiple signals; the combination may produce unexpected results

---

## 5. Ladder Issues

### Error: `No OHLCV data for FFN26:1H`

**Cause:** Data not fetched/cached before generating ladder.

**Fix:** Fetch data first:
```bash
POST /market-data/ingest
{
  "product_key": "fed_funds",
  "symbols": ["FFN26"],
  "timeframe": "1H",
  "compute_indicators": true
}
```

### Error: `Need ATR or DCW to generate ladder`

**Cause:** Indicators not computed or insufficient data for ATR/DCW.

**Fix:** Ensure at least 20+ bars are fetched and indicators are computed.

### All ladder levels at same price

**Cause:** Event regime (single entry) or spacing rounded to zero.

**Fix:**
- Check regime — event regime forces single entry
- Check if ATR/DCW is very small (tight market)
- Try a longer timeframe for wider spacing

### Ladder risk too high

**Cause:** ATR-based stops are too wide for the lot count.

**Fix:**
- Reduce `max_lots` in the request
- Use a shorter timeframe (tighter ATR)
- Adjust stop multiplier in `STRATEGY_DEFAULTS`

---

## 6. Frontend Issues

### Blank page / no data displayed

**Cause:** JavaScript error or API call failure.

**Fix:**
- Open browser DevTools (F12) → Console tab
- Look for JavaScript errors
- Check Network tab for failed API calls
- Verify the server is running on the expected port

### Chart not rendering

**Cause:** TradingView Lightweight Charts CDN not loaded or no OHLCV data.

**Fix:**
- Check browser console for CDN loading errors
- Ensure OHLCV data is fetched before opening the dashboard
- Try a hard refresh (Ctrl+Shift+R)

### Snapshots page shows empty

**Cause:** No data has been fetched yet.

**Fix:** Fetch data via the dashboard or API before viewing snapshots.

---

## 7. Docker Issues

### Container exits immediately

**Cause:** Missing `.env` file or configuration error.

**Fix:**
```bash
# Check container logs
docker-compose logs strategy-planner

# Ensure .env exists
copy .env.example .env
```

### Container unhealthy

**Cause:** Health check failing — application not responding on port 8000.

**Fix:**
```bash
# Check if app is actually running inside container
docker-compose exec strategy-planner curl http://localhost:8000/health

# Check logs for startup errors
docker-compose logs strategy-planner
```

### Config changes not reflected

**Cause:** `@lru_cache` caches config at startup.

**Fix:** Restart the container:
```bash
docker-compose restart strategy-planner
```

---

## 8. Test Issues

### Tests fail with `ImportError`

**Cause:** Running tests from wrong directory.

**Fix:**
```bash
cd StrategyPlanner
python -m pytest app/tests/ -v
```

### Tests fail with stale cache

**Cause:** Cache not being cleared between tests.

**Fix:** Ensure `conftest.py` has the `reset_cache` autouse fixture. If adding new tests, use the `seeded_cache` fixture for tests that need pre-populated data.

### Async test warnings

**Cause:** Missing `pytest-asyncio` configuration.

**Fix:** Ensure `pytest.ini` or `pyproject.toml` has:
```ini
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

---

## 9. Performance Issues

### Slow indicator computation

**Cause:** Large bar count (5000+ bars) with many indicators.

**Fix:**
- Reduce `MAX_BARS_PER_REQUEST` in `.env`
- Fetch fewer bars per request
- Indicator computation for 500 bars should be < 100ms

### Slow API responses

**Cause:** External API latency.

**Fix:**
- Increase `QH_API_TIMEOUT` in `.env`
- Check network latency to API server
- Use cached data where possible (don't refetch unnecessarily)
