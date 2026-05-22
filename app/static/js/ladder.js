/**
 * Alpine.js app for the Adaptive Strategy Ladder page.
 */
function ladderApp() {
  return {
    productKey: 'fed_funds',
    symbol: '',
    timeframe: '1H',
    strategy: 'trend_fed_repricing',
    direction: '',
    maxLevels: 5,
    loading: false,
    error: '',
    ladder: null,
    warnings: [],
    strategies: [],
    availableSymbols: [],
    products: {},

    async init() {
      await this.loadStrategies();
      await this.loadContracts();
    },

    async loadStrategies() {
      try {
        const resp = await fetch('/ladder/strategies');
        const data = await resp.json();
        this.strategies = data.strategies || [];
        if (this.strategies.length && !this.strategy) {
          this.strategy = this.strategies[0].name;
        }
      } catch (e) {
        console.error('Failed to load strategies', e);
      }
    },

    async loadContracts() {
      try {
        const resp = await fetch('/market-data/snapshots');
        const data = await resp.json();
        const symbols = [];
        if (data.snapshots && typeof data.snapshots === 'object') {
          for (const key of Object.keys(data.snapshots)) {
            symbols.push(key);
          }
        }
        if (data.spreads && typeof data.spreads === 'object') {
          for (const key of Object.keys(data.spreads)) {
            symbols.push(key);
          }
        }
        if (symbols.length === 0) {
          symbols.push('FFN26', 'FFQ26', 'FFU26', 'FFN26-FFQ26', 'FFQ26-FFU26');
        }
        this.availableSymbols = symbols;
        if (symbols.length && !this.symbol) {
          this.symbol = symbols[0];
        }
      } catch (e) {
        this.availableSymbols = ['FFN26', 'FFQ26', 'FFN26-FFQ26'];
        if (!this.symbol) this.symbol = this.availableSymbols[0];
      }
    },

    async generate() {
      this.loading = true;
      this.error = '';
      this.ladder = null;
      this.warnings = [];

      try {
        const body = {
          product_key: this.productKey,
          symbol: this.symbol,
          timeframe: this.timeframe,
          strategy: this.strategy,
          max_levels: this.maxLevels,
        };
        if (this.direction) {
          body.direction = this.direction;
        }

        const resp = await fetch('/ladder/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        const data = await resp.json();

        if (data.success && data.ladder) {
          this.ladder = data.ladder;
          this.warnings = data.warnings || [];
        } else {
          this.error = (data.errors && data.errors[0]) || 'Failed to generate ladder';
        }
      } catch (e) {
        this.error = 'Request failed: ' + e.message;
      } finally {
        this.loading = false;
      }
    },
  };
}
