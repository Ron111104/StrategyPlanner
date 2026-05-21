/**
 * Risk Module
 * Ladder generation, position sizing, risk profile computation, and scenario planning.
 */
document.addEventListener('DOMContentLoaded', function () {
    const api = new ApiClient();

    /**
     * Generate and display a ladder plan.
     */
    async function generateLadder(params) {
        try {
            const result = await api.generateLadder(params);
            return result;
        } catch (err) {
            console.error('Ladder generation failed:', err);
            showNotification('Ladder generation failed: ' + err.message, 'error');
            throw err;
        }
    }

    /**
     * Compute position size based on risk parameters.
     */
    async function computePositionSize(params) {
        try {
            const result = await api.computeSizing(params);
            return result;
        } catch (err) {
            console.error('Sizing computation failed:', err);
            showNotification('Sizing failed: ' + err.message, 'error');
            throw err;
        }
    }

    /**
     * Compute a full risk profile.
     */
    async function computeRiskProfile(params) {
        try {
            const result = await api.computeRiskProfile(params);
            return result;
        } catch (err) {
            console.error('Risk profile computation failed:', err);
            showNotification('Risk profile failed: ' + err.message, 'error');
            throw err;
        }
    }

    /**
     * Render a visual ladder display.
     */
    function renderLadderVisual(ladder, containerId) {
        const container = document.getElementById(containerId);
        if (!container || !ladder) return;

        const allLevels = [];

        (ladder.entry_levels || []).forEach(l => allLevels.push({ ...l, type: 'entry', color: '#22d3ee' }));
        (ladder.stop_levels || []).forEach(l => allLevels.push({ ...l, type: 'stop', color: '#fb7185' }));
        (ladder.target_levels || []).forEach(l => allLevels.push({ ...l, type: 'target', color: '#34d399' }));

        allLevels.sort((a, b) => b.price - a.price);

        const maxPrice = Math.max(...allLevels.map(l => l.price));
        const minPrice = Math.min(...allLevels.map(l => l.price));
        const range = maxPrice - minPrice || 0.01;

        container.innerHTML = allLevels.map(level => {
            const position = ((maxPrice - level.price) / range * 80) + 10;
            return `
                <div class="flex items-center gap-3 py-1" style="padding-left: ${position}%">
                    <div class="w-3 h-3 rounded-full" style="background: ${level.color}"></div>
                    <span class="text-xs font-mono" style="color: ${level.color}">${level.price.toFixed(3)}</span>
                    <span class="text-xs text-gray-500">${level.label} (${level.size} lots)</span>
                </div>
            `;
        }).join('');
    }

    /**
     * Compute scenario P&L for a given trade setup.
     */
    function computeScenarioPnl(entry, target, direction, size, tickSize, tickValue) {
        const dir = direction === 'long' ? 1 : -1;
        const ticks = Math.round((target - entry) * dir / tickSize);
        const pnl = ticks * tickValue * size;
        return { ticks, pnl };
    }

    /**
     * Compute expected value across weighted scenarios.
     */
    function computeExpectedValue(scenarios) {
        let ev = 0;
        let totalProb = 0;
        for (const scenario of scenarios) {
            ev += scenario.pnl * (scenario.probability / 100);
            totalProb += scenario.probability;
        }
        return { expectedValue: ev, totalProbability: totalProb };
    }

    /**
     * Save account configuration.
     */
    async function saveAccountConfig(config) {
        try {
            await api.updateAccountConfig(config);
            showNotification('Account configuration saved', 'success');
        } catch (err) {
            console.error('Config save failed:', err);
            showNotification('Failed to save config: ' + err.message, 'error');
        }
    }

    // Expose functions globally
    window.generateLadder = generateLadder;
    window.computePositionSize = computePositionSize;
    window.computeRiskProfile = computeRiskProfile;
    window.renderLadderVisual = renderLadderVisual;
    window.computeScenarioPnl = computeScenarioPnl;
    window.computeExpectedValue = computeExpectedValue;
    window.saveAccountConfig = saveAccountConfig;
});
