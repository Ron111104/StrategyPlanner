/**
 * Risk page Alpine.js application.
 */
function riskApp() {
    return {
        product: 'fed_funds',
        symbol: 'FFN26',
        direction: 'long',
        timeframe: '1H',
        entry: 95.750,
        stop: 95.700,
        target: 95.850,
        result: null,
        accountConfig: {
            max_position_lots: 100,
            max_risk_per_trade_usd: 50000,
            max_daily_risk_usd: 200000,
            default_slippage_ticks: 1,
            default_commission_per_lot: 2.50,
        },

        async init() {
            try {
                const config = await API.getAccountConfig();
                this.accountConfig = { ...this.accountConfig, ...config };
            } catch (e) { /* use defaults */ }
        },

        async computeRisk() {
            try {
                this.result = await API.getRiskAssessment(
                    this.symbol, this.direction, this.entry, this.stop, this.target,
                    this.product, this.timeframe
                );
            } catch (e) {
                alert('Risk computation error: ' + e.message);
            }
        },

        async saveAccountConfig() {
            try {
                await API.updateAccountConfig(this.accountConfig);
                alert('Account configuration saved');
            } catch (e) {
                alert('Error saving config: ' + e.message);
            }
        },
    };
}
