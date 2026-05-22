/**
 * TradingView Lightweight Charts wrapper for the platform.
 */
const ChartManager = {
    charts: {},
    series: {},

    createChart(containerId, options = {}) {
        const container = document.getElementById(containerId);
        if (!container) return null;

        // Remove existing chart
        if (this.charts[containerId]) {
            this.charts[containerId].remove();
        }

        const defaultOpts = {
            layout: {
                background: { color: '#111827' },
                textColor: '#9ca3af',
                fontSize: 10,
                fontFamily: "'JetBrains Mono', monospace",
            },
            grid: {
                vertLines: { color: '#1e293b' },
                horzLines: { color: '#1e293b' },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: { color: '#3b82f6', width: 1, style: 2, labelBackgroundColor: '#3b82f6' },
                horzLine: { color: '#3b82f6', width: 1, style: 2, labelBackgroundColor: '#3b82f6' },
            },
            rightPriceScale: {
                borderColor: '#1e293b',
                scaleMargins: { top: 0.1, bottom: 0.1 },
            },
            timeScale: {
                borderColor: '#1e293b',
                timeVisible: true,
                secondsVisible: false,
            },
            handleScroll: { vertTouchDrag: false },
        };

        const chart = LightweightCharts.createChart(container, { ...defaultOpts, ...options });
        this.charts[containerId] = chart;
        this.series[containerId] = {};

        // Resize observer
        const resizeObserver = new ResizeObserver(() => {
            chart.applyOptions({ width: container.clientWidth });
        });
        resizeObserver.observe(container);

        return chart;
    },

    addCandlestickSeries(containerId, data, options = {}) {
        const chart = this.charts[containerId];
        if (!chart) return null;

        const defaultOpts = {
            upColor: '#10b981',
            downColor: '#ef4444',
            borderDownColor: '#ef4444',
            borderUpColor: '#10b981',
            wickDownColor: '#ef4444',
            wickUpColor: '#10b981',
        };

        const series = chart.addCandlestickSeries({ ...defaultOpts, ...options });
        series.setData(data);
        this.series[containerId].candles = series;
        chart.timeScale().fitContent();
        return series;
    },

    addLineSeries(containerId, key, data, options = {}) {
        const chart = this.charts[containerId];
        if (!chart) return null;

        const defaultOpts = {
            lineWidth: 1,
            crosshairMarkerVisible: false,
        };

        const series = chart.addLineSeries({ ...defaultOpts, ...options });
        series.setData(data);
        this.series[containerId][key] = series;
        return series;
    },

    addAreaBand(containerId, key, upperData, lowerData, options = {}) {
        const chart = this.charts[containerId];
        if (!chart) return null;

        const upperSeries = chart.addLineSeries({
            lineWidth: 1,
            color: options.color || 'rgba(59,130,246,0.4)',
            crosshairMarkerVisible: false,
            lastValueVisible: false,
            priceLineVisible: false,
        });
        upperSeries.setData(upperData);

        const lowerSeries = chart.addLineSeries({
            lineWidth: 1,
            color: options.color || 'rgba(59,130,246,0.4)',
            crosshairMarkerVisible: false,
            lastValueVisible: false,
            priceLineVisible: false,
        });
        lowerSeries.setData(lowerData);

        this.series[containerId][key + '_upper'] = upperSeries;
        this.series[containerId][key + '_lower'] = lowerSeries;
        return { upper: upperSeries, lower: lowerSeries };
    },

    addMarkers(containerId, markers) {
        const candles = this.series[containerId]?.candles;
        if (!candles) return;
        candles.setMarkers(markers);
    },

    addPriceLine(containerId, seriesKey, price, options = {}) {
        const series = this.series[containerId]?.[seriesKey || 'candles'];
        if (!series) return null;
        return series.createPriceLine({
            price: price,
            color: options.color || '#3b82f6',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: true,
            title: options.title || '',
            ...options,
        });
    },

    removeSeries(containerId, key) {
        const chart = this.charts[containerId];
        const series = this.series[containerId]?.[key];
        if (chart && series) {
            chart.removeSeries(series);
            delete this.series[containerId][key];
        }
    },

    clearAllOverlays(containerId) {
        const chart = this.charts[containerId];
        if (!chart) return;
        const seriesMap = this.series[containerId] || {};
        for (const [key, series] of Object.entries(seriesMap)) {
            if (key !== 'candles') {
                chart.removeSeries(series);
            }
        }
        this.series[containerId] = { candles: seriesMap.candles };
    },

    barsToChartData(bars) {
        return bars.map(b => ({
            time: Utils.timestampToUnix(b.timestamp),
            open: b.open,
            high: b.high,
            low: b.low,
            close: b.close,
        })).sort((a, b) => a.time - b.time);
    },

    indicatorToLineData(indicator) {
        if (!indicator || !indicator.timestamps || !indicator.values) return [];
        return indicator.timestamps.map((t, i) => ({
            time: Utils.timestampToUnix(t),
            value: indicator.values[i],
        })).sort((a, b) => a.time - b.time);
    },

    bandToLineData(indicator, band) {
        if (!indicator || !indicator.timestamps || !indicator[band]) return [];
        return indicator.timestamps.map((t, i) => ({
            time: Utils.timestampToUnix(t),
            value: indicator[band][i],
        })).sort((a, b) => a.time - b.time);
    },

    destroy(containerId) {
        if (this.charts[containerId]) {
            this.charts[containerId].remove();
            delete this.charts[containerId];
            delete this.series[containerId];
        }
    },
};
