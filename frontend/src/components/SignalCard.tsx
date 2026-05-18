import { motion } from 'framer-motion'
import type { StrategySignal } from '../types'

const dirBadge = { long: 'badge-long', short: 'badge-short', neutral: 'badge-neutral' }

interface Props { signal: StrategySignal; onClick?: () => void; isSelected?: boolean }

export default function SignalCard({ signal, onClick, isSelected }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`signal-card cursor-pointer ${isSelected ? 'border-terminal-accent ring-1 ring-terminal-accent/30' : ''}`}
      onClick={onClick}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="font-mono font-semibold text-sm">{signal.strategy_name}</span>
          <span className={dirBadge[signal.direction]}>{signal.direction.toUpperCase()}</span>
        </div>
        <div className="flex items-center gap-2">
          {signal.caution_flag && <span className="text-terminal-warning text-xs">⚠ CAUTION</span>}
          <span className="font-mono text-sm text-terminal-accent">{(signal.confidence_score * 100).toFixed(0)}%</span>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3 text-xs">
        <div><span className="stat-label">Entry</span><div className="font-mono text-terminal-text mt-0.5">{signal.entry_price.toFixed(3)}</div></div>
        <div><span className="stat-label">Stop</span><div className="font-mono text-terminal-danger mt-0.5">{signal.stop_price.toFixed(3)}</div></div>
        <div><span className="stat-label">Target 1</span><div className="font-mono text-terminal-success mt-0.5">{signal.targets[0]?.toFixed(3)}</div></div>
        <div><span className="stat-label">R:R</span><div className="font-mono text-terminal-text mt-0.5">{signal.risk_calc.risk_reward_ratio?.toFixed(1) ?? '—'}</div></div>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-3 text-xs">
        <div><span className="stat-label">Lots</span><div className="font-mono mt-0.5">{signal.risk_calc.max_lots}</div></div>
        <div><span className="stat-label">Risk</span><div className="font-mono mt-0.5">${signal.risk_calc.total_risk.toFixed(0)}</div></div>
        <div><span className="stat-label">Cost</span><div className="font-mono text-terminal-text-dim mt-0.5">${signal.risk_calc.round_trip_cost.toFixed(0)}</div></div>
      </div>

      {signal.trigger_conditions.length > 0 && (
        <div className="mt-3 pt-2 border-t border-terminal-border/50">
          {signal.trigger_conditions.map((c, i) => (
            <div key={i} className="text-[10px] text-terminal-text-dim leading-relaxed">• {c}</div>
          ))}
        </div>
      )}
    </motion.div>
  )
}
