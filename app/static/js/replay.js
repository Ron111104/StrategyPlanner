/**
 * Replay page Alpine.js application.
 */
function replayApp() {
    return {
        selectedProduct: 'fed_funds',
        selectedSymbol: '',
        selectedTimeframe: '1H',
        availableSymbols: [],
        allBars: [],
        replayIdx: 0,
        totalBars: 0,
        playing: false,
        speed: 500,
        playInterval: null,
        notes: '',
        currentBar: null,
        currentTimestamp: '',
        barChange: 0,

        get progressPct() {
            return this.totalBars > 0 ? ((this.replayIdx + 1) / this.totalBars * 100) : 0;
        },

        init() {
            this.onProductChange();
        },

        onProductChange() {
            const configs = {
                fed_funds: { contracts: ['FFN26','FFQ26','FFU26','FFV26','FFX26','FFZ26'], spreads: ['FFN26-FFQ26','FFQ26-FFU26'] },
                sofr: { contracts: ['SFRM26','SFRU26','SFRZ26','SFRH27'], spreads: ['SFRM26-SFRU26','SFRU26-SFRZ26'] },
            };
            const c = configs[this.selectedProduct] || { contracts: [], spreads: [] };
            this.availableSymbols = [...c.contracts, ...c.spreads];
            if (this.availableSymbols.length > 0) this.selectedSymbol = this.availableSymbols[0];
        },

        async loadData() {
            if (!this.selectedSymbol) return;
            this.stopPlay();

            try {
                // Ingest data first
                let symbols = [this.selectedSymbol];
                if (this.selectedSymbol.includes('-')) {
                    const [f, b] = this.selectedSymbol.split('-');
                    symbols = [f, b, this.selectedSymbol];
                }
                await API.ingestMarketData(this.selectedProduct, symbols, this.selectedTimeframe);

                const data = await API.getOHLCV(this.selectedSymbol, this.selectedTimeframe);
                this.allBars = data.bars || [];
                this.totalBars = this.allBars.length;
                this.replayIdx = Math.min(20, this.totalBars - 1);

                ChartManager.createChart('replay-chart');
                this.renderUpTo(this.replayIdx);
            } catch (e) {
                alert('Load error: ' + e.message);
            }
        },

        renderUpTo(idx) {
            if (this.allBars.length === 0) return;
            const slice = this.allBars.slice(0, idx + 1);
            const chartData = ChartManager.barsToChartData(slice);

            ChartManager.createChart('replay-chart');
            ChartManager.addCandlestickSeries('replay-chart', chartData);

            const bar = this.allBars[idx];
            this.currentBar = bar;
            this.currentTimestamp = bar ? Utils.timestampToUTC(bar.timestamp) : '';
            this.barChange = idx > 0 ? (bar.close - this.allBars[idx - 1].close) : 0;
        },

        replayNext() {
            if (this.replayIdx < this.totalBars - 1) {
                this.replayIdx++;
                this.renderUpTo(this.replayIdx);
            } else {
                this.stopPlay();
            }
        },

        replayPrev() {
            if (this.replayIdx > 0) {
                this.replayIdx--;
                this.renderUpTo(this.replayIdx);
            }
        },

        seekTo(idx) {
            this.replayIdx = Number(idx);
            this.renderUpTo(this.replayIdx);
        },

        togglePlay() {
            if (this.playing) {
                this.stopPlay();
            } else {
                this.startPlay();
            }
        },

        startPlay() {
            this.playing = true;
            this.playInterval = setInterval(() => {
                this.replayNext();
                if (this.replayIdx >= this.totalBars - 1) this.stopPlay();
            }, this.speed);
        },

        stopPlay() {
            this.playing = false;
            if (this.playInterval) {
                clearInterval(this.playInterval);
                this.playInterval = null;
            }
        },
    };
}
