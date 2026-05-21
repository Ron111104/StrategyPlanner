/**
 * ReplayEngine - Historical Playback with Signal Evaluation
 * Bar-by-bar chart update, regime tracking, and statistics accumulation.
 */
class ReplayEngine {
    constructor(chartContainerId) {
        this.chartManager = null;
        this.chartContainerId = chartContainerId;
        this.bars = [];
        this.currentIndex = 0;
        this.isPlaying = false;
        this.speed = 1;
        this.playInterval = null;
        this.signals = [];
        this.regimeHistory = [];
        this.stats = {
            totalSignals: 0,
            longSignals: 0,
            shortSignals: 0,
            regimeChanges: 0,
        };
        this.onBarUpdate = null;
        this.onSignal = null;
        this.onRegimeChange = null;
    }

    /**
     * Load historical bars for replay.
     */
    async loadBars(product, timeframe) {
        const api = new ApiClient();
        try {
            const bars = await api.fetchBars(product, timeframe);
            this.bars = bars || [];
            this.currentIndex = Math.min(51, this.bars.length);
            this.signals = [];
            this.regimeHistory = [];
            this.stats = { totalSignals: 0, longSignals: 0, shortSignals: 0, regimeChanges: 0 };
            this.updateChart();
            return this.bars.length;
        } catch (err) {
            console.error('Failed to load replay bars:', err);
            throw err;
        }
    }

    /**
     * Initialize or rebuild the chart with bars up to currentIndex.
     */
    updateChart() {
        if (this.bars.length === 0) return;

        const visibleBars = this.bars.slice(0, this.currentIndex + 1);

        if (this.chartManager) {
            this.chartManager.destroy();
        }

        this.chartManager = new ChartManager(this.chartContainerId, { height: 384 });
        this.chartManager.addCandlestickSeries(visibleBars);

        // Add accumulated signal markers
        if (this.signals.length > 0) {
            this.chartManager.addSignalMarkers(this.signals);
        }

        if (this.onBarUpdate) {
            this.onBarUpdate(visibleBars[visibleBars.length - 1], this.currentIndex, this.bars.length);
        }
    }

    /**
     * Start playback.
     */
    play() {
        if (this.isPlaying) return;
        this.isPlaying = true;

        const intervalMs = Math.max(50, 1000 / this.speed);

        this.playInterval = setInterval(() => {
            if (this.currentIndex < this.bars.length - 1) {
                this.stepForward();
            } else {
                this.pause();
            }
        }, intervalMs);
    }

    /**
     * Pause playback.
     */
    pause() {
        this.isPlaying = false;
        if (this.playInterval) {
            clearInterval(this.playInterval);
            this.playInterval = null;
        }
    }

    /**
     * Step forward one bar.
     */
    stepForward() {
        if (this.currentIndex >= this.bars.length - 1) return;
        this.currentIndex++;
        this.updateChart();
    }

    /**
     * Step backward one bar.
     */
    stepBack() {
        if (this.currentIndex <= 51) return;
        this.currentIndex--;
        this.updateChart();
    }

    /**
     * Reset to beginning.
     */
    reset() {
        this.pause();
        this.currentIndex = Math.min(51, this.bars.length);
        this.signals = [];
        this.regimeHistory = [];
        this.stats = { totalSignals: 0, longSignals: 0, shortSignals: 0, regimeChanges: 0 };
        this.updateChart();
    }

    /**
     * Set playback speed.
     */
    setSpeed(speed) {
        this.speed = Math.max(0.1, Math.min(10, speed));
        if (this.isPlaying) {
            this.pause();
            this.play();
        }
    }

    /**
     * Add a signal at the current bar.
     */
    addSignal(signal) {
        const bar = this.bars[this.currentIndex];
        if (!bar) return;

        const enrichedSignal = {
            ...signal,
            timestamp: bar.timestamp,
            time: typeof bar.timestamp === 'string' ? Math.floor(new Date(bar.timestamp).getTime() / 1000) : bar.timestamp,
        };

        this.signals.push(enrichedSignal);
        this.stats.totalSignals++;

        if (signal.direction === 'long') {
            this.stats.longSignals++;
        } else {
            this.stats.shortSignals++;
        }

        if (this.onSignal) {
            this.onSignal(enrichedSignal);
        }
    }

    /**
     * Record a regime change.
     */
    recordRegimeChange(regime) {
        const bar = this.bars[this.currentIndex];
        if (!bar) return;

        this.regimeHistory.push({
            regime: regime,
            timestamp: bar.timestamp,
            barIndex: this.currentIndex,
        });

        this.stats.regimeChanges++;

        if (this.onRegimeChange) {
            this.onRegimeChange(regime, this.currentIndex);
        }
    }

    /**
     * Get current bar data.
     */
    getCurrentBar() {
        return this.bars[this.currentIndex] || null;
    }

    /**
     * Get progress as percentage.
     */
    getProgress() {
        if (this.bars.length === 0) return 0;
        return (this.currentIndex / (this.bars.length - 1)) * 100;
    }

    /**
     * Destroy and cleanup.
     */
    destroy() {
        this.pause();
        if (this.chartManager) {
            this.chartManager.destroy();
            this.chartManager = null;
        }
    }
}

// Export
if (typeof window !== 'undefined') {
    window.ReplayEngine = ReplayEngine;
}
