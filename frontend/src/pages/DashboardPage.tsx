import { useAppStore } from '../store/useAppStore'
import { useContracts, useRegime, useStrategyDefs, useHealth } from '../hooks/useApi'
import Sidebar from '../layouts/Sidebar'
import ControlBar from '../components/ControlBar'
import Watchlist from '../components/Watchlist'
import RegimePanel from '../components/RegimePanel'
import SignalCard from '../components/SignalCard'
import RiskPanel from '../components/RiskPanel'
import StrategyHeatmap from '../components/StrategyHeatmap'
import CandlestickChart from '../charts/CandlestickChart'
import SpreadChart from '../charts/SpreadChart'
import { motion, AnimatePresence } from 'framer-motion'

// Demo chart data generator for initial render
function generateDemoData(count: number, basePrice: number) {
  const data = []
  let price = basePrice
  for (let i = 0; i < count; i++) {
    const d = new Date(2026, 0, 1)
    d.setHours(d.getHours() + i)
    const change = (Math.random() - 0.48) * 0.02
    const open = price
    const close = price + change
    const high = Math.max(open, close) + Math.random() * 0.01
    const low = Math.min(open, close) - Math.random() * 0.008
    data.push({ time: d.toISOString().slice(0, 10) + ' ' + d.toISOString().slice(11, 16), open: +open.toFixed(3), high: +high.toFixed(3), low: +low.toFixed(3), close: +close.toFixed(3) })
    price = close
  }
  return data
}

function generateSpreadDemo(count: number) {
  const data = []
  let bp = 5.0
  for (let i = 0; i < count; i++) {
    const d = new Date(2026, 0, 1)
    d.setHours(d.getHours() + i)
    bp += (Math.random() - 0.5) * 0.8
    data.push({ time: d.toISOString().slice(0, 10) + ' ' + d.toISOString().slice(11, 16), value: +bp.toFixed(1) })
  }
  return data
}

const demoCandles = generateDemoData(120, 96.5)
const demoSpread = generateSpreadDemo(120)

export default function DashboardPage() {
  const { signals, selectedSignal, setSelectedSignal, activePanel, selectedProduct, toggleSidebar } = useAppStore()
  const { data: contracts } = useContracts()
  const { data: regime } = useRegime()
  const { data: strategyDefs } = useStrategyDefs()
  const { data: health } = useHealth()

  return (
    <div className="h-screen flex overflow-hidden bg-terminal-bg">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header Bar */}
        <header className="h-10 bg-terminal-surface border-b border-terminal-border flex items-center px-4 justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            <button onClick={toggleSidebar} className="text-terminal-text-dim hover:text-terminal-text text-sm">☰</button>
            <span className="text-xs text-terminal-text-dim font-mono uppercase tracking-widest">{activePanel}</span>
          </div>
          <div className="flex items-center gap-3 text-[10px] text-terminal-text-dim font-mono">
            {health && <span className="text-terminal-success">● CONNECTED</span>}
            <span>{new Date().toLocaleTimeString()}</span>
          </div>
        </header>

        {/* Control Bar */}
        <div className="flex-shrink-0">
          <ControlBar />
        </div>

        {/* Main Content */}
        <main className="flex-1 overflow-y-auto p-3 space-y-3">
          <AnimatePresence mode="wait">
            {activePanel === 'dashboard' && (
              <motion.div key="dash" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-3">
                <div className="grid grid-cols-12 gap-3">
                  {/* Left: Watchlist + Regime */}
                  <div className="col-span-3 space-y-3">
                    <Watchlist contracts={contracts ?? null} />
                    <RegimePanel regime={regime ?? null} />
                  </div>

                  {/* Center: Charts */}
                  <div className="col-span-6 space-y-3">
                    <CandlestickChart data={demoCandles} title={`${selectedProduct} — Price Chart`} height={350} />
                    <SpreadChart data={demoSpread} title="Calendar Spread (bp)" height={200} />
                  </div>

                  {/* Right: Signals + Risk */}
                  <div className="col-span-3 space-y-3">
                    <div className="glass-panel p-3">
                      <span className="stat-label">Active Signals ({signals.length})</span>
                      <div className="mt-2 space-y-2 max-h-[360px] overflow-y-auto">
                        {signals.length === 0 && <div className="text-xs text-terminal-text-dim py-4 text-center">Run evaluation to generate signals</div>}
                        {signals.map(s => (
                          <SignalCard key={s.signal_id} signal={s} isSelected={selectedSignal?.signal_id === s.signal_id} onClick={() => setSelectedSignal(s)} />
                        ))}
                      </div>
                    </div>
                    <RiskPanel signal={selectedSignal} />
                  </div>
                </div>
              </motion.div>
            )}

            {activePanel === 'strategies' && (
              <motion.div key="strat" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <div className="grid grid-cols-12 gap-3">
                  <div className="col-span-6">
                    <StrategyHeatmap strategies={strategyDefs?.strategies ?? []} />
                  </div>
                  <div className="col-span-6">
                    <div className="glass-panel p-4">
                      <span className="stat-label">Evaluation Console</span>
                      <div className="mt-3 text-xs text-terminal-text-dim">Select a product and timeframe, then click Evaluate to run all strategies. Results will appear in the Signals panel.</div>
                      <div className="mt-4 grid grid-cols-2 gap-3">
                        <div className="p-3 rounded-md bg-terminal-bg border border-terminal-border">
                          <span className="stat-label">Total Strategies</span>
                          <div className="stat-value mt-1">{strategyDefs?.strategies.length ?? 0}</div>
                        </div>
                        <div className="p-3 rounded-md bg-terminal-bg border border-terminal-border">
                          <span className="stat-label">Active Signals</span>
                          <div className="stat-value mt-1">{signals.length}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {activePanel === 'signals' && (
              <motion.div key="sigs" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <div className="grid grid-cols-12 gap-3">
                  <div className="col-span-8 space-y-2">
                    {signals.length === 0 && <div className="glass-panel p-8 text-center text-sm text-terminal-text-dim">No signals generated. Fetch data and run evaluation first.</div>}
                    {signals.map(s => <SignalCard key={s.signal_id} signal={s} isSelected={selectedSignal?.signal_id === s.signal_id} onClick={() => setSelectedSignal(s)} />)}
                  </div>
                  <div className="col-span-4">
                    <RiskPanel signal={selectedSignal} />
                  </div>
                </div>
              </motion.div>
            )}

            {activePanel === 'risk' && (
              <motion.div key="risk" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <RiskPanel signal={selectedSignal} />
              </motion.div>
            )}

            {activePanel === 'regime' && (
              <motion.div key="regime" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <div className="max-w-lg">
                  <RegimePanel regime={regime ?? null} />
                </div>
              </motion.div>
            )}

            {(activePanel === 'events' || activePanel === 'settings') && (
              <motion.div key="other" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <div className="glass-panel p-8 text-center">
                  <span className="text-sm text-terminal-text-dim">{activePanel === 'events' ? 'Event Calendar — Configure macro events via the /api/regime/update endpoint' : 'Settings — Configure via contracts.yaml, strategy_settings.yaml, and .env'}</span>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </main>

        {/* Status Bar */}
        <footer className="h-6 bg-terminal-surface border-t border-terminal-border flex items-center px-4 text-[10px] text-terminal-text-dim font-mono justify-between flex-shrink-0">
          <span>ZQ Strategy Planner v1.0.0</span>
          <div className="flex gap-4">
            <span>Product: {selectedProduct}</span>
            <span>Regime: {regime?.regime?.toUpperCase() ?? 'N/A'}</span>
            <span>Signals: {signals.length}</span>
          </div>
        </footer>
      </div>
    </div>
  )
}
