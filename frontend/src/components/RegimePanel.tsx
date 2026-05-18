import { motion } from 'framer-motion'
import type { RegimeState } from '../types'

const regimeColors: Record<string, string> = {
  event: 'bg-red-500/20 text-red-400 border-red-500/30',
  volatility: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  trend: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  range: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  no_signal: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
}

const biasColors: Record<string, string> = {
  hawkish: 'text-red-400', dovish: 'text-emerald-400', neutral: 'text-slate-400',
}

export default function RegimePanel({ regime }: { regime: RegimeState | null }) {
  if (!regime) return <div className="glass-panel p-4 animate-pulse"><div className="h-20 bg-terminal-border/20 rounded" /></div>

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass-panel p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="stat-label">Market Regime</span>
        {regime.is_manual_override && <span className="text-[10px] text-terminal-warning">MANUAL</span>}
      </div>

      <div className="flex items-center gap-3 mb-3">
        <span className={`px-3 py-1.5 rounded-md border text-sm font-mono font-semibold ${regimeColors[regime.regime]}`}>
          {regime.regime.toUpperCase()}
        </span>
        <span className={`text-sm font-mono ${biasColors[regime.macro_bias]}`}>
          {regime.macro_bias.toUpperCase()}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3 text-xs">
        <div><span className="stat-label">Confidence</span><div className="font-mono mt-0.5">{(regime.confidence * 100).toFixed(0)}%</div></div>
        <div><span className="stat-label">Volatility</span><div className="font-mono mt-0.5">{regime.volatility_level.toFixed(4)}</div></div>
        <div><span className="stat-label">Event Lock</span><div className={`font-mono mt-0.5 ${regime.event_lock_active ? 'text-terminal-danger' : 'text-terminal-success'}`}>{regime.event_lock_active ? 'ACTIVE' : 'CLEAR'}</div></div>
      </div>

      {regime.classification_reason && (
        <div className="mt-2 text-[10px] text-terminal-text-dim">{regime.classification_reason}</div>
      )}

      {regime.active_events.length > 0 && (
        <div className="mt-3 pt-2 border-t border-terminal-border/50">
          <span className="stat-label">Active Events</span>
          {regime.active_events.map(e => (
            <div key={e.event_id} className="mt-1 text-xs flex items-center gap-2">
              <span className="text-terminal-warning">⚡</span>
              <span className="font-mono">{e.name}</span>
              <span className="text-terminal-text-dim">{e.impact}</span>
            </div>
          ))}
        </div>
      )}
    </motion.div>
  )
}
