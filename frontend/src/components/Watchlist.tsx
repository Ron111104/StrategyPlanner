import type { ContractsResponse } from '../types'
import { useAppStore } from '../store/useAppStore'

export default function Watchlist({ contracts }: { contracts: ContractsResponse | null }) {
  const { selectedProduct, setSelectedProduct } = useAppStore()
  if (!contracts) return null

  return (
    <div className="glass-panel">
      <div className="px-3 py-2 border-b border-terminal-border text-xs text-terminal-text-dim font-mono uppercase tracking-wider">Watchlist</div>
      <div className="max-h-64 overflow-y-auto">
        {contracts.outrights.map(c => (
          <button key={c.symbol} onClick={() => setSelectedProduct(c.symbol)}
            className={`w-full flex items-center justify-between px-3 py-2 text-xs hover:bg-terminal-border/30 transition-colors ${selectedProduct === c.symbol ? 'bg-terminal-accent/10 border-l-2 border-terminal-accent' : ''}`}>
            <span className="font-mono font-medium">{c.symbol}</span>
            <span className="text-terminal-text-dim">{c.description}</span>
          </button>
        ))}
        <div className="px-3 py-1 text-[10px] text-terminal-text-dim uppercase bg-terminal-border/20">Spreads</div>
        {contracts.spreads.map(c => (
          <button key={c.symbol} onClick={() => setSelectedProduct(c.symbol)}
            className={`w-full flex items-center justify-between px-3 py-2 text-xs hover:bg-terminal-border/30 transition-colors ${selectedProduct === c.symbol ? 'bg-terminal-accent/10 border-l-2 border-terminal-accent' : ''}`}>
            <span className="font-mono font-medium text-violet-400">{c.symbol}</span>
            <span className="text-terminal-text-dim">{c.description}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
