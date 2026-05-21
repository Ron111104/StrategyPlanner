/**
 * Dashboard Module
 * Main dashboard initialization and interactive state management.
 */
document.addEventListener('DOMContentLoaded', function () {
    // Initialize dashboard chart
    const mainChartContainer = document.getElementById('main-chart');
    let dashboardChart = null;

    if (mainChartContainer) {
        dashboardChart = new ChartManager('main-chart', { height: 320 });
    }

    // Dashboard Alpine.js data store
    if (typeof Alpine !== 'undefined') {
        document.addEventListener('alpine:init', () => {
            Alpine.store('dashboard', {
                selectedProduct: '',
                selectedTimeframe: '1H',
                isLoading: false,
                lastUpdate: null,
                watchlistData: [],
                signals: [],

                async selectProduct(product) {
                    this.selectedProduct = product;
                    await this.loadChart(product);
                },

                async loadChart(product) {
                    if (!product || !dashboardChart) return;
                    this.isLoading = true;

                    try {
                        const api = new ApiClient();
                        const bars = await api.fetchBars(product, this.selectedTimeframe);

                        if (bars && bars.length > 0) {
                            dashboardChart.destroy();
                            dashboardChart = new ChartManager('main-chart', { height: 320 });
                            dashboardChart.addCandlestickSeries(bars);
                        }
                    } catch (err) {
                        console.error('Failed to load chart:', err);
                    } finally {
                        this.isLoading = false;
                        this.lastUpdate = new Date().toLocaleTimeString();
                    }
                },

                async refreshAll() {
                    if (this.selectedProduct) {
                        await this.loadChart(this.selectedProduct);
                    }
                }
            });
        });
    }

    // Auto-refresh every 30 seconds
    let refreshInterval = setInterval(() => {
        // Trigger HTMX refresh for watchlist
        const watchlistEl = document.getElementById('watchlist-container');
        if (watchlistEl && typeof htmx !== 'undefined') {
            htmx.trigger(watchlistEl, 'refresh');
        }
    }, 30000);

    // Watchlist row click handler
    document.addEventListener('click', function (e) {
        const row = e.target.closest('[data-product]');
        if (row) {
            const product = row.dataset.product;
            if (typeof Alpine !== 'undefined' && Alpine.store('dashboard')) {
                Alpine.store('dashboard').selectProduct(product);
            }

            // Highlight active row
            document.querySelectorAll('[data-product]').forEach(r => r.classList.remove('ring-1', 'ring-cyan-500/50'));
            row.classList.add('ring-1', 'ring-cyan-500/50');
        }
    });

    // Heatmap cell click handler
    document.addEventListener('click', function (e) {
        const cell = e.target.closest('[data-heatmap-product]');
        if (cell) {
            const product = cell.dataset.heatmapProduct;
            window.location.href = `/strategy?product=${product}`;
        }
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', function (e) {
        // R to refresh
        if (e.key === 'r' && !e.ctrlKey && !e.metaKey && e.target.tagName !== 'INPUT' && e.target.tagName !== 'SELECT') {
            if (typeof Alpine !== 'undefined' && Alpine.store('dashboard')) {
                Alpine.store('dashboard').refreshAll();
            }
        }
    });

    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
        clearInterval(refreshInterval);
        if (dashboardChart) {
            dashboardChart.destroy();
        }
    });
});
