import type { StrategyDefinition } from '../types'

const regimeColors: Record<string, string> = {
  event: 'bg-red-500/20 text-red-400', volatility: 'bg-amber-500/20 text-amber-400',
  trend: 'bg-blue-500/20 text-blue-400', range: 'bg-emerald-500/20 text-emerald-400',
}

export default function StrategyHeatmap({ strategies }: { strategies: StrategyDefinition[] }) {
  return (
    <div className="glass-panel p-4">
      <span className="stat-label">Strategy Matrix</span>
      <div className="mt-3 space-y-2">
        {strategies.map(s => (
          <div key={s.name} className="flex items-center gap-2 p-2 rounded-md hover:bg-terminal-border/20 transition-colors">
            <div className="w-1 h-8 rounded-full bg-terminal-accent/60" />
            <div className="flex-1 min-w-0">
              <div className="text-xs font-mono font-medium truncate">{s.name}</div>
              <div className="text-[10px] text-terminal-text-dim truncate">{s.description}</div>
            </div>
            <div className="flex gap-1 flex-shrink-0">
              {s.regimes.map(r => (
                <span key={r} className={`px-1.5 py-0.5 text-[9px] rounded ${regimeColors[r] || 'bg-slate-500/20 text-slate-400'}`}>
                  {r.slice(0, 3).toUpperCase()}
                </span>
              ))}
            </div>
            <span className="text-[10px] text-terminal-text-dim font-mono w-8 text-right">{s.risk_multiplier}x</span>
          </div>
        ))}
      </div>
    </div>
  )
}
