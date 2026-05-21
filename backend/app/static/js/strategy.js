/**
 * Strategy Module
 * Strategy evaluation form handling, result display, chart updates, and indicator overlays.
 */
document.addEventListener('DOMContentLoaded', function () {
    let strategyChart = null;

    // Initialize strategy chart if container exists
    const chartContainer = document.getElementById('strategy-chart');
    if (chartContainer) {
        strategyChart = new ChartManager('strategy-chart', { height: 384 });
    }

    /**
     * Update the chart with evaluation results including signals and indicators.
     */
    function updateChartWithResults(bars, signals, indicators) {
        if (!strategyChart || !bars || bars.length === 0) return;

        // Rebuild chart
        strategyChart.destroy();
        strategyChart = new ChartManager('strategy-chart', { height: 384 });
        strategyChart.addCandlestickSeries(bars);

        // Add signal markers
        if (signals && signals.length > 0) {
            strategyChart.addSignalMarkers(signals);

            // Add entry/stop/target lines for first signal
            const signal = signals[0];
            strategyChart.addPriceLine(signal.entry_price, 'Entry', '#22d3ee');
            strategyChart.addPriceLine(signal.stop_price, 'Stop', '#fb7185');
            strategyChart.addPriceLine(signal.target_price, 'Target', '#34d399');

            // Add ladder if available
            if (signal.ladder) {
                strategyChart.addLadderLevels(signal.ladder);
            }
        }
    }

    /**
     * Handle strategy evaluation form submission.
     */
    async function handleEvaluate(product, timeframe, regimeOverride, biasOverride) {
        const api = new ApiClient();

        try {
            // First fetch bars for chart
            let bars = [];
            try {
                const barsResult = await api.fetchBars(product, timeframe);
                bars = barsResult || [];
            } catch (e) {
                console.warn('Could not fetch bars for chart:', e);
            }

            // Evaluate strategy
            const request = {
                product: product,
                timeframe: timeframe,
                regime_override: regimeOverride || null,
                bias_override: biasOverride || null,
            };

            const result = await api.evaluateStrategy(request);

            // Update chart
            if (bars.length > 0) {
                updateChartWithResults(bars, result.signals, null);
            }

            return result;
        } catch (err) {
            console.error('Strategy evaluation failed:', err);
            throw err;
        }
    }

    /**
     * Render signal cards in the results panel.
     */
    function renderSignalCards(signals, container) {
        if (!container) return;

        if (!signals || signals.length === 0) {
            container.innerHTML = `
                <div class="text-center py-8 text-gray-500">
                    <p class="text-sm">No signals generated</p>
                </div>
            `;
            return;
        }

        container.innerHTML = signals.map(signal => `
            <div class="bg-[#1a1f2e] rounded-lg border border-gray-700/50 p-4 signal-card-animate">
                <div class="flex items-center justify-between mb-3">
                    <h4 class="text-sm font-medium text-gray-200">${signal.strategy_name}</h4>
                    <span class="px-2 py-0.5 rounded text-xs font-bold ${signal.direction === 'long' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}">
                        ${signal.direction.toUpperCase()}
                    </span>
                </div>
                <div class="grid grid-cols-3 gap-3 text-xs">
                    <div><span class="text-gray-500 block">Entry</span><span class="font-mono text-cyan-400">${signal.entry_price.toFixed(3)}</span></div>
                    <div><span class="text-gray-500 block">Stop</span><span class="font-mono text-rose-400">${signal.stop_price.toFixed(3)}</span></div>
                    <div><span class="text-gray-500 block">Target</span><span class="font-mono text-emerald-400">${signal.target_price.toFixed(3)}</span></div>
                </div>
                <div class="mt-2 flex justify-between text-xs">
                    <span class="text-gray-500">R:R ${signal.risk_reward_ratio}:1</span>
                    <span class="text-gray-500">Conf: ${(signal.confidence * 100).toFixed(1)}%</span>
                </div>
            </div>
        `).join('');
    }

    // Expose for Alpine.js
    window.handleEvaluate = handleEvaluate;
    window.renderSignalCards = renderSignalCards;
    window.updateChartWithResults = updateChartWithResults;

    // Cleanup
    window.addEventListener('beforeunload', () => {
        if (strategyChart) strategyChart.destroy();
    });
});
