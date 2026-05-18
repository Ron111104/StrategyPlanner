import { useState } from 'react'
import { useAppStore } from '../store/useAppStore'
import { useFetchMarketData, useEvaluateStrategies } from '../hooks/useApi'
import type { Timeframe, MarketRegime } from '../types'

const TIMEFRAMES: Timeframe[] = ['1M', '5M', '15M', '1H', '4H', '1D']
const REGIMES: (MarketRegime | 'auto')[] = ['auto', 'trend', 'range', 'volatility', 'event']

export default function ControlBar() {
  const { selectedProduct, selectedTimeframe, setSelectedTimeframe, setSignals } = useAppStore()
  const fetchMutation = useFetchMarketData()
  const evalMutation = useEvaluateStrategies()
  const [regimeOverride, setRegimeOverride] = useState<MarketRegime | 'auto'>('auto')

  const handleFetch = () => {
    fetchMutation.mutate({ products: [selectedProduct], timeframe: selectedTimeframe })
  }

  const handleEvaluate = () => {
    evalMutation.mutate(
      { product: selectedProduct, timeframe: selectedTimeframe, regime_override: regimeOverride === 'auto' ? undefined : regimeOverride },
      { onSuccess: (data) => setSignals(data.signals) }
    )
  }

  return (
    <div className="glass-panel px-4 py-2 flex items-center gap-3 flex-wrap">
      <span className="font-mono font-semibold text-sm text-terminal-accent">{selectedProduct}</span>

      <div className="flex gap-1 bg-terminal-bg rounded-md p-0.5">
        {TIMEFRAMES.map(tf => (
          <button key={tf} onClick={() => setSelectedTimeframe(tf)}
            className={`px-2 py-1 text-[10px] font-mono rounded transition-colors ${selectedTimeframe === tf ? 'bg-terminal-accent text-white' : 'text-terminal-text-dim hover:text-terminal-text'}`}>
            {tf}
          </button>
        ))}
      </div>

      <select value={regimeOverride} onChange={e => setRegimeOverride(e.target.value as MarketRegime | 'auto')}
        className="input-field text-xs py-1 bg-terminal-bg">
        {REGIMES.map(r => <option key={r} value={r}>{r === 'auto' ? 'Auto Regime' : r.toUpperCase()}</option>)}
      </select>

      <button onClick={handleFetch} disabled={fetchMutation.isPending} className="btn-primary text-xs">
        {fetchMutation.isPending ? 'Fetching...' : '📡 Fetch Data'}
      </button>

      <button onClick={handleEvaluate} disabled={evalMutation.isPending} className="btn-primary text-xs bg-emerald-600 hover:bg-emerald-500">
        {evalMutation.isPending ? 'Evaluating...' : '⚡ Evaluate'}
      </button>

      {evalMutation.data && (
        <span className="text-[10px] text-terminal-text-dim font-mono">
          {evalMutation.data.signals.length} signals • {evalMutation.data.evaluation_time_ms.toFixed(1)}ms
        </span>
      )}
    </div>
  )
}
