/**
 * API client for the Strategy Planning Platform.
 */
const API = {
    async post(url, body) {
        const resp = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || err.error || 'Request failed');
        }
        return resp.json();
    },

    async put(url, body) {
        const resp = await fetch(url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || err.error || 'Request failed');
        }
        return resp.json();
    },

    async get(url) {
        const resp = await fetch(url);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || err.error || 'Request failed');
        }
        return resp.json();
    },

    // Market Data
    fetchMarketData(productKey, symbols, timeframe) {
        return this.post('/market-data/fetch', {
            product_key: productKey,
            symbols: symbols,
            timeframe: timeframe,
        });
    },

    ingestMarketData(productKey, symbols, timeframe, computeIndicators = true) {
        return this.post('/market-data/ingest', {
            product_key: productKey,
            symbols: symbols,
            timeframe: timeframe,
            compute_indicators: computeIndicators,
        });
    },

    getSnapshots() {
        return this.get('/market-data/snapshots');
    },

    getOHLCV(symbol, timeframe) {
        return this.get(`/market-data/ohlcv/${symbol}/${timeframe}`);
    },

    getIndicators(symbol, timeframe) {
        return this.get(`/market-data/indicators/${symbol}/${timeframe}`);
    },

    // Strategy
    evaluateStrategies(productKey, symbols, timeframe, strategies = null, regime = null, macroBias = null) {
        const body = {
            product_key: productKey,
            symbols: symbols,
            timeframe: timeframe,
        };
        if (strategies) body.strategies = strategies;
        if (regime) body.regime = regime;
        if (macroBias) body.macro_bias = macroBias;
        return this.post('/strategy/evaluate', body);
    },

    getSignals() {
        return this.get('/strategy/signals');
    },

    getRiskAssessment(symbol, direction, entry, stop, target, productKey, timeframe) {
        return this.get(
            `/strategy/risk/${symbol}?direction=${direction}&entry=${entry}&stop=${stop}&target=${target}&product_key=${productKey}&timeframe=${timeframe}`
        );
    },

    // Regime
    updateRegime(regime, macroBias, notes = '') {
        return this.put('/regime/update', {
            regime: regime,
            macro_bias: macroBias,
            notes: notes,
        });
    },

    getRegime() {
        return this.get('/regime/current');
    },

    suggestRegime(symbol, timeframe) {
        return this.get(`/regime/suggest/${symbol}/${timeframe}`);
    },

    // Account
    updateAccountConfig(config) {
        return this.put('/account/config', config);
    },

    getAccountConfig() {
        return this.get('/account/config');
    },
};
