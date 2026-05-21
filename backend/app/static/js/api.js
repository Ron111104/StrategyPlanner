/* ============================================================
   CME Fed Funds Futures (ZQ) Strategy Planning Platform
   API Client Module
   ============================================================ */

/**
 * Custom error class for API errors.
 * Captures HTTP status, response body, and endpoint information.
 */
class ApiError extends Error {
  /**
   * @param {string} message - Human-readable error description
   * @param {number} status - HTTP status code
   * @param {string} endpoint - The API endpoint that failed
   * @param {*} body - Parsed response body (if available)
   */
  constructor(message, status, endpoint, body = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.endpoint = endpoint;
    this.body = body;
    this.timestamp = new Date().toISOString();
  }

  /**
   * Check if the error is a client-side error (4xx)
   * @returns {boolean}
   */
  isClientError() {
    return this.status >= 400 && this.status < 500;
  }

  /**
   * Check if the error is a server-side error (5xx)
   * @returns {boolean}
   */
  isServerError() {
    return this.status >= 500;
  }

  /**
   * Check if the error is a network/timeout issue (status 0)
   * @returns {boolean}
   */
  isNetworkError() {
    return this.status === 0;
  }
}

/**
 * API Client for the ZQ Strategy Planning Platform.
 * Wraps all REST endpoints under /api/ with consistent error handling,
 * logging, and JSON serialization.
 */
class ApiClient {
  /**
   * @param {Object} options
   * @param {string} [options.baseUrl='/api'] - Base URL prefix for all API calls
   * @param {number} [options.timeout=30000] - Request timeout in ms
   * @param {boolean} [options.debug=false] - Enable verbose request/response logging
   */
  constructor(options = {}) {
    this.baseUrl = options.baseUrl || '/api';
    this.timeout = options.timeout || 30000;
    this.debug = options.debug || false;
    this._requestId = 0;
  }

  /* ── Internal helpers ─────────────────────────────────── */

  /**
   * Generate a monotonically increasing request ID for log correlation.
   * @returns {number}
   */
  _nextRequestId() {
    return ++this._requestId;
  }

  /**
   * Log a request (debug mode only).
   * @param {number} id - Request ID
   * @param {string} method - HTTP method
   * @param {string} url - Full URL
   * @param {*} body - Request body
   */
  _logRequest(id, method, url, body) {
    if (!this.debug) return;
    console.groupCollapsed(
      `%c→ API #${id} %c${method} %c${url}`,
      'color:#22d3ee', 'color:#fbbf24;font-weight:700', 'color:#9ca3af'
    );
    if (body) console.log('Body:', body);
    console.log('Time:', new Date().toISOString());
    console.groupEnd();
  }

  /**
   * Log a response (debug mode only).
   * @param {number} id - Request ID
   * @param {number} status - HTTP status
   * @param {*} data - Parsed response
   * @param {number} durationMs - Round-trip time in ms
   */
  _logResponse(id, status, data, durationMs) {
    if (!this.debug) return;
    const color = status >= 400 ? '#fb7185' : '#34d399';
    console.groupCollapsed(
      `%c← API #${id} %c${status} %c(${durationMs}ms)`,
      'color:#22d3ee', `color:${color};font-weight:700`, 'color:#9ca3af'
    );
    console.log('Data:', data);
    console.groupEnd();
  }

  /**
   * Core fetch wrapper with timeout, logging, and error handling.
   * @param {string} endpoint - Path relative to baseUrl
   * @param {Object} options - Fetch options
   * @returns {Promise<*>} Parsed JSON response
   * @throws {ApiError}
   */
  async _request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const reqId = this._nextRequestId();
    const method = options.method || 'GET';
    const start = performance.now();

    const headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...(options.headers || {}),
    };

    const fetchOptions = {
      method,
      headers,
      ...(options.body !== undefined ? { body: JSON.stringify(options.body) } : {}),
    };

    this._logRequest(reqId, method, url, options.body);

    // Build an AbortController for timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);
    fetchOptions.signal = controller.signal;

    let response;
    try {
      response = await fetch(url, fetchOptions);
    } catch (err) {
      clearTimeout(timeoutId);
      const duration = Math.round(performance.now() - start);
      if (err.name === 'AbortError') {
        const apiErr = new ApiError(
          `Request timed out after ${this.timeout}ms`,
          0, endpoint
        );
        this._logResponse(reqId, 0, { error: apiErr.message }, duration);
        throw apiErr;
      }
      const apiErr = new ApiError(
        `Network error: ${err.message}`,
        0, endpoint
      );
      this._logResponse(reqId, 0, { error: apiErr.message }, duration);
      throw apiErr;
    } finally {
      clearTimeout(timeoutId);
    }

    const duration = Math.round(performance.now() - start);

    // Parse response body (may be empty for 204, etc.)
    let data = null;
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      try {
        data = await response.json();
      } catch {
        data = null;
      }
    } else {
      try {
        const text = await response.text();
        // Attempt JSON parse even if header is wrong
        data = text ? JSON.parse(text) : null;
      } catch {
        data = null;
      }
    }

    this._logResponse(reqId, response.status, data, duration);

    if (!response.ok) {
      const message =
        (data && (data.detail || data.message || data.error)) ||
        `HTTP ${response.status} on ${method} ${endpoint}`;
      throw new ApiError(message, response.status, endpoint, data);
    }

    return data;
  }

  /**
   * Convenience GET.
   * @param {string} endpoint
   * @param {Object} [params] - Query parameters
   * @returns {Promise<*>}
   */
  async _get(endpoint, params) {
    let url = endpoint;
    if (params) {
      const qs = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== null) {
          qs.append(key, String(value));
        }
      }
      const qsStr = qs.toString();
      if (qsStr) url += `?${qsStr}`;
    }
    return this._request(url);
  }

  /**
   * Convenience POST.
   * @param {string} endpoint
   * @param {*} body
   * @returns {Promise<*>}
   */
  async _post(endpoint, body) {
    return this._request(endpoint, { method: 'POST', body });
  }

  /**
   * Convenience PUT.
   * @param {string} endpoint
   * @param {*} body
   * @returns {Promise<*>}
   */
  async _put(endpoint, body) {
    return this._request(endpoint, { method: 'PUT', body });
  }

  /**
   * Convenience PATCH.
   * @param {string} endpoint
   * @param {*} body
   * @returns {Promise<*>}
   */
  async _patch(endpoint, body) {
    return this._request(endpoint, { method: 'PATCH', body });
  }

  /* ── Public API Methods ───────────────────────────────── */

  /**
   * Fetch real-time snapshot for a product (e.g. ZQM2025).
   * @param {string} product - Product symbol
   * @returns {Promise<Object>} Snapshot data
   */
  async fetchSnapshot(product) {
    return this._get(`/snapshot/${encodeURIComponent(product)}`);
  }

  /**
   * Fetch OHLCV bar data.
   * @param {string} product - Product symbol
   * @param {string} timeframe - e.g. '1D', '1H', '5m'
   * @returns {Promise<Object>} Bar data array
   */
  async fetchBars(product, timeframe) {
    return this._get(`/bars/${encodeURIComponent(product)}`, { timeframe });
  }

  /**
   * Fetch calendar spread between front and back contracts.
   * @param {string} front - Front month symbol
   * @param {string} back - Back month symbol
   * @returns {Promise<Object>} Spread data
   */
  async fetchSpread(front, back) {
    return this._get('/spread', { front, back });
  }

  /**
   * Evaluate a strategy (signals, indicators, regime).
   * @param {Object} request - Strategy evaluation request
   * @param {string} request.product - Product symbol
   * @param {string} request.strategy - Strategy name
   * @param {Object} [request.params] - Strategy parameters
   * @returns {Promise<Object>} Evaluation results
   */
  async evaluateStrategy(request) {
    return this._post('/strategy/evaluate', request);
  }

  /**
   * Update the market regime classification for a product.
   * @param {string} product - Product symbol
   * @param {Object} data - Regime override data
   * @param {string} data.regime - Regime type
   * @param {string} [data.notes] - Override notes
   * @returns {Promise<Object>} Updated regime
   */
  async updateRegime(product, data) {
    return this._put(`/regime/${encodeURIComponent(product)}`, data);
  }

  /**
   * Update account configuration (margin, risk limits, etc.).
   * @param {Object} config - Account configuration object
   * @returns {Promise<Object>} Updated config
   */
  async updateAccountConfig(config) {
    return this._put('/account/config', config);
  }

  /**
   * Compute position sizing based on risk parameters.
   * @param {Object} request - Sizing request
   * @param {number} request.accountSize - Account equity
   * @param {number} request.riskPercent - Risk per trade (%)
   * @param {number} request.entryPrice - Entry price
   * @param {number} request.stopPrice - Stop price
   * @param {number} [request.tickValue] - Tick value in USD
   * @returns {Promise<Object>} Sizing result
   */
  async computeSizing(request) {
    return this._post('/risk/sizing', request);
  }

  /**
   * Compute full risk profile for a position/portfolio.
   * @param {Object} request - Risk profile request
   * @returns {Promise<Object>} Risk profile
   */
  async computeRiskProfile(request) {
    return this._post('/risk/profile', request);
  }

  /**
   * Generate a price ladder for scaling in/out.
   * @param {Object} request - Ladder generation request
   * @param {number} request.startPrice - Starting price level
   * @param {number} request.endPrice - Ending price level
   * @param {number} request.steps - Number of rungs
   * @param {string} [request.distribution] - 'linear', 'geometric', 'front-weighted'
   * @returns {Promise<Object>} Generated ladder
   */
  async generateLadder(request) {
    return this._post('/risk/ladder', request);
  }

  /**
   * Health check endpoint.
   * @returns {Promise<Object>} Health status
   */
  async getHealth() {
    return this._get('/health');
  }

  /**
   * Fetch market data (generic, with filtering).
   * @param {Object} request - Query parameters
   * @returns {Promise<Object>} Market data
   */
  async fetchMarketData(request) {
    return this._get('/market-data', request);
  }

  /**
   * Ingest external market data.
   * @param {Object} data - Market data payload
   * @returns {Promise<Object>} Ingest result
   */
  async ingestMarketData(data) {
    return this._post('/market-data/ingest', data);
  }

  /**
   * Get all configured strategies.
   * @returns {Promise<Object>} Strategies list
   */
  async getStrategies() {
    return this._get('/strategies');
  }

  /**
   * Get current regime classification for a product.
   * @param {string} product - Product symbol
   * @returns {Promise<Object>} Regime data
   */
  async getRegime(product) {
    return this._get(`/regime/${encodeURIComponent(product)}`);
  }
}

/* ── Singleton Export ──────────────────────────────────────── */

/**
 * Default shared API client instance.
 * Debug mode is enabled if URL contains ?debug or #debug.
 */
const api = new ApiClient({
  debug:
    window.location.search.includes('debug') ||
    window.location.hash.includes('debug'),
});

// Expose globally for non-module contexts (HTMX inline scripts, Alpine, etc.)
window.ApiClient = ApiClient;
window.ApiError = ApiError;
window.api = api;
