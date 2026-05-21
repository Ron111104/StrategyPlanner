/**
 * ChartManager - TradingView Lightweight Charts Integration
 * Institutional-grade charting with dark theme and full indicator support.
 */
class ChartManager {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        this.chart = null;
        this.candlestickSeries = null;
        this.lineSeries = {};
        this.areaSeries = {};
        this.markers = [];
        this.priceLines = [];
        this.options = options;

        if (this.container) {
            this.createChart();
        }
    }

    createChart() {
        if (!this.container || typeof LightweightCharts === 'undefined') {
            console.warn('Chart container not found or LightweightCharts not loaded');
            return null;
        }

        this.chart = LightweightCharts.createChart(this.container, {
            width: this.container.clientWidth,
            height: this.options.height || 384,
            layout: {
                background: { type: 'solid', color: '#0a0e17' },
                textColor: '#9ca3af',
                fontSize: 11,
                fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
            },
            grid: {
                vertLines: { color: '#1f293780' },
                horzLines: { color: '#1f293780' },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: { color: '#4b556380', width: 1, style: 2 },
                horzLine: { color: '#4b556380', width: 1, style: 2 },
            },
            rightPriceScale: {
                borderColor: '#1f2937',
                scaleMargins: { top: 0.1, bottom: 0.1 },
            },
            timeScale: {
                borderColor: '#1f2937',
                timeVisible: true,
                secondsVisible: false,
                rightOffset: 5,
                barSpacing: 8,
            },
            handleScroll: { vertTouchDrag: false },
        });

        // Auto-resize
        const resizeObserver = new ResizeObserver(entries => {
            for (const entry of entries) {
                const { width, height } = entry.contentRect;
                this.chart.applyOptions({ width, height });
            }
        });
        resizeObserver.observe(this.container);
        this._resizeObserver = resizeObserver;

        return this.chart;
    }

    addCandlestickSeries(data) {
        if (!this.chart) return null;

        this.candlestickSeries = this.chart.addCandlestickSeries({
            upColor: '#34d399',
            downColor: '#fb7185',
            borderUpColor: '#34d399',
            borderDownColor: '#fb7185',
            wickUpColor: '#34d39980',
            wickDownColor: '#fb718580',
        });

        const formatted = data.map(bar => ({
            time: typeof bar.timestamp === 'string' ? Math.floor(new Date(bar.timestamp).getTime() / 1000) : bar.timestamp || bar.time,
            open: bar.open,
            high: bar.high,
            low: bar.low,
            close: bar.close,
        })).sort((a, b) => a.time - b.time);

        this.candlestickSeries.setData(formatted);
        this.chart.timeScale().fitContent();
        return this.candlestickSeries;
    }

    addLineSeries(data, options = {}) {
        if (!this.chart) return null;

        const series = this.chart.addLineSeries({
            color: options.color || '#22d3ee',
            lineWidth: options.lineWidth || 1,
            lineStyle: options.lineStyle || 0,
            title: options.title || '',
            priceScaleId: options.priceScaleId || 'right',
            lastValueVisible: options.lastValueVisible !== false,
            priceLineVisible: options.priceLineVisible !== false,
        });

        const formatted = data.map(point => ({
            time: typeof point.time === 'string' ? Math.floor(new Date(point.time).getTime() / 1000) : point.time,
            value: point.value,
        })).sort((a, b) => a.time - b.time);

        series.setData(formatted);
        const key = options.title || `line_${Object.keys(this.lineSeries).length}`;
        this.lineSeries[key] = series;
        return series;
    }

    addSpreadSeries(data) {
        if (!this.chart) return null;

        const series = this.chart.addAreaSeries({
            topColor: '#22d3ee26',
            bottomColor: '#22d3ee05',
            lineColor: '#22d3ee',
            lineWidth: 2,
            title: 'Spread (bp)',
        });

        const formatted = data.map(point => ({
            time: typeof point.time === 'string' ? Math.floor(new Date(point.time).getTime() / 1000) : point.time,
            value: point.value || point.spread_bp,
        })).sort((a, b) => a.time - b.time);

        series.setData(formatted);
        this.areaSeries['spread'] = series;
        return series;
    }

    addATROverlay(data) {
        return this.addLineSeries(data, {
            color: '#fbbf24',
            lineWidth: 1,
            title: 'ATR',
            priceScaleId: 'atr',
            lastValueVisible: true,
        });
    }

    addDonchianOverlay(upper, lower, mid) {
        if (!this.chart) return;

        this.addLineSeries(upper, { color: '#34d39960', lineWidth: 1, title: 'DC Upper', lineStyle: 2 });
        this.addLineSeries(lower, { color: '#fb718560', lineWidth: 1, title: 'DC Lower', lineStyle: 2 });
        this.addLineSeries(mid, { color: '#9ca3af40', lineWidth: 1, title: 'DC Mid', lineStyle: 1 });
    }

    addBollingerOverlay(upper, lower, mid) {
        if (!this.chart) return;

        this.addLineSeries(upper, { color: '#fbbf2460', lineWidth: 1, title: 'BB Upper', lineStyle: 2 });
        this.addLineSeries(lower, { color: '#fbbf2460', lineWidth: 1, title: 'BB Lower', lineStyle: 2 });
        this.addLineSeries(mid, { color: '#fbbf24', lineWidth: 1, title: 'BB Mid' });
    }

    addMovingAverage(data, length, color = '#8b5cf6') {
        return this.addLineSeries(data, {
            color: color,
            lineWidth: 1,
            title: `MA${length}`,
        });
    }

    addSignalMarkers(signals) {
        if (!this.candlestickSeries || !signals || signals.length === 0) return;

        const markers = signals.map(signal => ({
            time: typeof signal.timestamp === 'string' ? Math.floor(new Date(signal.timestamp).getTime() / 1000) : signal.timestamp || signal.time,
            position: signal.direction === 'long' ? 'belowBar' : 'aboveBar',
            color: signal.direction === 'long' ? '#34d399' : '#fb7185',
            shape: signal.direction === 'long' ? 'arrowUp' : 'arrowDown',
            text: signal.strategy_name || signal.label || (signal.direction === 'long' ? 'BUY' : 'SELL'),
        })).sort((a, b) => a.time - b.time);

        this.candlestickSeries.setMarkers(markers);
        this.markers = markers;
    }

    addPriceLine(price, title, color) {
        if (!this.candlestickSeries) return null;

        const priceLine = this.candlestickSeries.createPriceLine({
            price: price,
            color: color,
            lineWidth: 1,
            lineStyle: 2,
            axisLabelVisible: true,
            title: title,
        });

        this.priceLines.push(priceLine);
        return priceLine;
    }

    addLadderLevels(ladder) {
        if (!ladder) return;

        // Clear existing price lines
        this.clearPriceLines();

        // Entry levels
        if (ladder.entry_levels) {
            ladder.entry_levels.forEach(level => {
                this.addPriceLine(level.price, level.label, '#22d3ee');
            });
        }

        // Stop levels
        if (ladder.stop_levels) {
            ladder.stop_levels.forEach(level => {
                this.addPriceLine(level.price, level.label, '#fb7185');
            });
        }

        // Target levels
        if (ladder.target_levels) {
            ladder.target_levels.forEach(level => {
                this.addPriceLine(level.price, level.label, '#34d399');
            });
        }
    }

    clearPriceLines() {
        if (this.candlestickSeries) {
            this.priceLines.forEach(line => {
                try { this.candlestickSeries.removePriceLine(line); } catch (e) { /* ignore */ }
            });
        }
        this.priceLines = [];
    }

    clearIndicators() {
        Object.values(this.lineSeries).forEach(series => {
            try { this.chart.removeSeries(series); } catch (e) { /* ignore */ }
        });
        this.lineSeries = {};

        Object.values(this.areaSeries).forEach(series => {
            try { this.chart.removeSeries(series); } catch (e) { /* ignore */ }
        });
        this.areaSeries = {};
    }

    setVisibleRange(from, to) {
        if (this.chart) {
            this.chart.timeScale().setVisibleRange({ from, to });
        }
    }

    resize() {
        if (this.chart && this.container) {
            this.chart.applyOptions({
                width: this.container.clientWidth,
                height: this.container.clientHeight,
            });
        }
    }

    destroy() {
        if (this._resizeObserver) {
            this._resizeObserver.disconnect();
        }
        if (this.chart) {
            this.chart.remove();
            this.chart = null;
        }
        this.candlestickSeries = null;
        this.lineSeries = {};
        this.areaSeries = {};
        this.markers = [];
        this.priceLines = [];
    }
}

// Export for module usage
if (typeof window !== 'undefined') {
    window.ChartManager = ChartManager;
}
