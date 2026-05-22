/**
 * Utility functions for the Strategy Planning Platform.
 */
const Utils = {
    formatPrice(value, decimals = 4) {
        if (value == null) return '—';
        return Number(value).toFixed(decimals);
    },

    formatBp(value) {
        if (value == null) return '—';
        const sign = value >= 0 ? '+' : '';
        return `${sign}${Number(value).toFixed(1)} bp`;
    },

    formatPct(value) {
        if (value == null) return '—';
        return `${(value * 100).toFixed(1)}%`;
    },

    formatUSD(value) {
        if (value == null) return '—';
        return `$${Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    },

    spreadBpFromPrices(front, back) {
        return Math.round((front - back) * 100 * 100) / 100;
    },

    ticksBetween(priceA, priceB, tickSize) {
        if (tickSize <= 0) return 0;
        return Math.round(Math.abs(priceA - priceB) / tickSize * 10000) / 10000;
    },

    timestampToUTC(ts) {
        const d = new Date(ts);
        return d.toISOString().slice(0, 19).replace('T', ' ');
    },

    timestampToUnix(ts) {
        return Math.floor(new Date(ts).getTime() / 1000);
    },

    directionColor(dir) {
        if (dir === 'long') return '#10b981';
        if (dir === 'short') return '#ef4444';
        return '#64748b';
    },

    debounce(fn, ms) {
        let timer;
        return function (...args) {
            clearTimeout(timer);
            timer = setTimeout(() => fn.apply(this, args), ms);
        };
    },

    // Products config parsed from the page
    _productsCache: null,
    getProducts() {
        if (this._productsCache) return this._productsCache;
        // Will be set by page-level JS
        return {};
    },
};
