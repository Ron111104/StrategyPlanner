/**
 * Strategy page Alpine.js application.
 */
function strategyApp() {
    return {
        selectedProduct: 'fed_funds',
        selectedSymbol: '',
        selectedTimeframe: '1H',
        availableSymbols: [],
        evalSignals: [],
        evalPlans: [],
        skippedStrats: [],
        showATR: false,
        showBB: true,
        showDC: false,
        showEMA: true,
        statusMsg: '',
        statusOk: true,

        async init() {
            this.onProductChange();
        },

        onProductChange() {
            // Build symbols list from product config embedded in page
            const productConfigs = {
                fed_funds: {
                    contracts: ['FFN26','FFQ26','FFU26','FFV26','FFX26','FFZ26','FFF27','FFG27','FFH27'],
                    spreads: ['FFN26-FFQ26','FFQ26-FFU26','FFU26-FFV26','FFV26-FFX26','FFX26-FFZ26'],
                },
                sofr: {
                    contracts: ['SFRM26','SFRU26','SFRZ26','SFRH27'],
                    spreads: ['SFRM26-SFRU26','SFRU26-SFRZ26','SFRZ26-SFRH27'],
                },
            };
            const config = productConfigs[this.selectedProduct] || { contracts: [], spreads: [] };
            this.availableSymbols = [...config.contracts, ...config.spreads];
            if (this.availableSymbols.length > 0 && !this.availableSymbols.includes(this.selectedSymbol)) {
                this.selectedSymbol = this.availableSymbols[0];
            }
        },

        async ingestAndEvaluate() {
            if (!this.selectedSymbol) return;
            this.statusMsg = 'Ingesting data and evaluating...';
            this.statusOk = true;
            this.evalSignals = [];
            this.evalPlans = [];
            this.skippedStrats = [];

            try {
                // Determine all legs needed
                let symbols = [this.selectedSymbol];
                if (this.selectedSymbol.includes('-')) {
                    const [front, back] = this.selectedSymbol.split('-');
                    symbols = [front, back, this.selectedSymbol];
                }

                // Ingest
                await API.ingestMarketData(this.selectedProduct, symbols, this.selectedTimeframe);

                // Load chart
                await this.loadChart();

                // Evaluate
                const evalResult = await API.evaluateStrategies(
                    this.selectedProduct, [this.selectedSymbol], this.selectedTimeframe
                );

                if (evalResult.results && evalResult.results.length > 0) {
                    const r = evalResult.results[0];
                    this.evalSignals = r.signals || [];
                    this.evalPlans = r.entry_exit_plans || [];
                    this.skippedStrats = r.skipped_strategies || [];

                    // Add signal markers to chart
                    this.addSignalMarkers();
                }

                this.statusMsg = `${this.evalSignals.length} signals from ${evalResult.results[0]?.evaluated_strategies?.length || 0} strategies`;
                this.statusOk = true;
            } catch (e) {
                this.statusMsg = 'Error: ' + e.message;
                this.statusOk = false;
            }
        },

        async loadChart() {
            try {
                const data = await API.getOHLCV(this.selectedSymbol, this.selectedTimeframe);
                if (!data.bars || data.bars.length === 0) return;

                const chartData = ChartManager.barsToChartData(data.bars);
                ChartManager.createChart('strategy-chart');
                ChartManager.addCandlestickSeries('strategy-chart', chartData);

                // Overlay indicators
                try {
                    const ind = await API.getIndicators(this.selectedSymbol, this.selectedTimeframe);
                    this.applyOverlays(ind);
                } catch (e) { /* no indicators */ }
            } catch (e) {
                console.warn('Chart load error:', e);
            }
        },

        applyOverlays(ind) {
            if (!ind) return;

            if (this.showEMA) {
                if (ind.ema?.['9']) {
                    ChartManager.addLineSeries('strategy-chart', 'ema9',
                        ChartManager.indicatorToLineData(ind.ema['9']),
                        { color: '#f59e0b', lineWidth: 1 });
                }
                if (ind.ema?.['21']) {
                    ChartManager.addLineSeries('strategy-chart', 'ema21',
                        ChartManager.indicatorToLineData(ind.ema['21']),
                        { color: '#8b5cf6', lineWidth: 1 });
                }
            }

            if (this.showBB && ind.bollinger) {
                if (ind.bollinger.upper_band) {
                    ChartManager.addLineSeries('strategy-chart', 'bb_upper',
                        ChartManager.bandToLineData(ind.bollinger, 'upper_band'),
                        { color: 'rgba(59,130,246,0.4)', lineWidth: 1 });
                }
                if (ind.bollinger.lower_band) {
                    ChartManager.addLineSeries('strategy-chart', 'bb_lower',
                        ChartManager.bandToLineData(ind.bollinger, 'lower_band'),
                        { color: 'rgba(59,130,246,0.4)', lineWidth: 1 });
                }
                ChartManager.addLineSeries('strategy-chart', 'bb_mid',
                    ChartManager.indicatorToLineData(ind.bollinger),
                    { color: 'rgba(59,130,246,0.6)', lineWidth: 1, lineStyle: 2 });
            }

            if (this.showDC && ind.donchian) {
                if (ind.donchian.upper_band) {
                    ChartManager.addLineSeries('strategy-chart', 'dc_upper',
                        ChartManager.bandToLineData(ind.donchian, 'upper_band'),
                        { color: 'rgba(16,185,129,0.4)', lineWidth: 1 });
                }
                if (ind.donchian.lower_band) {
                    ChartManager.addLineSeries('strategy-chart', 'dc_lower',
                        ChartManager.bandToLineData(ind.donchian, 'lower_band'),
                        { color: 'rgba(239,68,68,0.4)', lineWidth: 1 });
                }
            }
        },

        addSignalMarkers() {
            const markers = this.evalSignals.map(sig => ({
                time: Utils.timestampToUnix(sig.timestamp),
                position: sig.direction === 'long' ? 'belowBar' : 'aboveBar',
                color: sig.direction === 'long' ? '#10b981' : '#ef4444',
                shape: sig.direction === 'long' ? 'arrowUp' : 'arrowDown',
                text: sig.strategy_name.substring(0, 8),
            })).sort((a, b) => a.time - b.time);

            if (markers.length > 0) {
                ChartManager.addMarkers('strategy-chart', markers);
            }

            // Add entry/stop/target price lines
            this.evalSignals.forEach(sig => {
                if (sig.entry_price) {
                    ChartManager.addPriceLine('strategy-chart', 'candles', sig.entry_price, {
                        color: '#3b82f6', title: 'Entry', lineStyle: 2,
                    });
                }
                if (sig.stop_price) {
                    ChartManager.addPriceLine('strategy-chart', 'candles', sig.stop_price, {
                        color: '#ef4444', title: 'Stop', lineStyle: 2,
                    });
                }
                if (sig.target_price) {
                    ChartManager.addPriceLine('strategy-chart', 'candles', sig.target_price, {
                        color: '#10b981', title: 'Target', lineStyle: 2,
                    });
                }
            });
        },
    };
}
