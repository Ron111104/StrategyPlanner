/**
 * Dashboard page Alpine.js application.
 */
function dashboardApp() {
    return {
        selectedProduct: 'fed_funds',
        selectedTimeframe: '1H',
        regime: 'range',
        macroBias: 'neutral',
        chartSymbol: '',
        chartType: 'candles',
        signalCards: [],
        statusMsg: '',
        statusOk: true,
        products: {},

        async init() {
            // Load products config from page data
            try {
                const resp = await API.getRegime();
                this.regime = resp.regime;
                this.macroBias = resp.macro_bias;
            } catch (e) { /* use defaults */ }

            try {
                const signals = await API.getSignals();
                this.signalCards = signals.cards || [];
            } catch (e) { /* empty */ }
        },

        onProductChange() {
            this.chartSymbol = '';
            this.signalCards = [];
        },

        async fetchData() {
            this.statusMsg = 'Fetching market data...';
            this.statusOk = true;
            try {
                // Get product contracts from backend
                const productSelect = document.querySelector('select[x-model="selectedProduct"]');
                const productKey = this.selectedProduct;

                // Fetch all contracts + spreads for the product
                const resp = await fetch(`/market-data/snapshots`);
                const snapshotData = await resp.json();

                // Build symbols list from the page-rendered watchlist
                const rows = document.querySelectorAll('#watchlist-body tr td:first-child, #spread-body tr td:first-child');
                let symbols = [];
                rows.forEach(td => { if (td.textContent.trim()) symbols.push(td.textContent.trim()); });

                if (symbols.length === 0) {
                    // Fallback: try to read from product config via contracts.yaml structure
                    symbols = ['FFN26', 'FFQ26', 'FFU26', 'FFN26-FFQ26', 'FFQ26-FFU26'];
                }

                const result = await API.ingestMarketData(productKey, symbols, this.selectedTimeframe);
                this.statusMsg = `Loaded ${result.symbols_loaded.length} symbols`;
                this.statusOk = true;

                if (!this.chartSymbol && result.symbols_loaded.length > 0) {
                    this.selectSymbol(result.symbols_loaded[0]);
                }

                // Refresh page to update watchlists
                setTimeout(() => location.reload(), 500);
            } catch (e) {
                this.statusMsg = 'Error: ' + e.message;
                this.statusOk = false;
            }
        },

        async evaluateStrategies() {
            this.statusMsg = 'Evaluating strategies...';
            this.statusOk = true;
            try {
                const rows = document.querySelectorAll('#watchlist-body tr td:first-child, #spread-body tr td:first-child');
                let symbols = [];
                rows.forEach(td => { if (td.textContent.trim()) symbols.push(td.textContent.trim()); });

                if (symbols.length === 0) {
                    symbols = ['FFN26', 'FFQ26', 'FFU26'];
                }

                await API.evaluateStrategies(
                    this.selectedProduct, symbols, this.selectedTimeframe,
                    null, this.regime, this.macroBias
                );

                const signals = await API.getSignals();
                this.signalCards = signals.cards || [];
                this.statusMsg = `Evaluated: ${this.signalCards.length} instruments, ${signals.cards.reduce((a, c) => a + c.signals.length, 0)} signals`;
                this.statusOk = true;
            } catch (e) {
                this.statusMsg = 'Error: ' + e.message;
                this.statusOk = false;
            }
        },

        async updateRegime() {
            try {
                await API.updateRegime(this.regime, this.macroBias);
            } catch (e) {
                this.statusMsg = 'Regime update failed: ' + e.message;
                this.statusOk = false;
            }
        },

        async selectSymbol(symbol) {
            this.chartSymbol = symbol;
            try {
                const data = await API.getOHLCV(symbol, this.selectedTimeframe);
                if (data.bars && data.bars.length > 0) {
                    const chartData = ChartManager.barsToChartData(data.bars);
                    ChartManager.createChart('main-chart');
                    ChartManager.addCandlestickSeries('main-chart', chartData);

                    // Try loading indicators
                    try {
                        const ind = await API.getIndicators(symbol, this.selectedTimeframe);
                        this.overlayIndicators('main-chart', ind);
                    } catch (e) { /* no indicators yet */ }
                }
            } catch (e) {
                // No data cached for this symbol
            }
        },

        overlayIndicators(chartId, ind) {
            if (!ind) return;

            // EMA 9
            if (ind.ema && ind.ema['9']) {
                ChartManager.addLineSeries(chartId, 'ema9',
                    ChartManager.indicatorToLineData(ind.ema['9']),
                    { color: '#f59e0b', lineWidth: 1 }
                );
            }
            // EMA 21
            if (ind.ema && ind.ema['21']) {
                ChartManager.addLineSeries(chartId, 'ema21',
                    ChartManager.indicatorToLineData(ind.ema['21']),
                    { color: '#8b5cf6', lineWidth: 1 }
                );
            }
            // Bollinger Bands
            if (ind.bollinger) {
                ChartManager.addLineSeries(chartId, 'bb_mid',
                    ChartManager.indicatorToLineData(ind.bollinger),
                    { color: 'rgba(59,130,246,0.5)', lineWidth: 1, lineStyle: 2 }
                );
                if (ind.bollinger.upper_band) {
                    ChartManager.addLineSeries(chartId, 'bb_upper',
                        ChartManager.bandToLineData(ind.bollinger, 'upper_band'),
                        { color: 'rgba(59,130,246,0.3)', lineWidth: 1 }
                    );
                }
                if (ind.bollinger.lower_band) {
                    ChartManager.addLineSeries(chartId, 'bb_lower',
                        ChartManager.bandToLineData(ind.bollinger, 'lower_band'),
                        { color: 'rgba(59,130,246,0.3)', lineWidth: 1 }
                    );
                }
            }
        },
    };
}
