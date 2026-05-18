import type { StrategySignal } from '../types'

export default function RiskPanel({ signal }: { signal: StrategySignal | null }) {
  if (!signal) return (
    <div className="glass-panel p-4">
      <span className="stat-label">Risk Profile</span>
      <div className="mt-3 text-xs text-terminal-text-dim">Select a signal to view risk details</div>
    </div>
  )

  const rc = signal.risk_calc
  const lp = signal.ladder_plan

  return (
    <div className="glass-panel p-4 space-y-4">
      <div className="flex items-center justify-between">
        <span className="stat-label">Risk Profile</span>
        <span className="font-mono text-xs text-terminal-accent">{signal.strategy_name}</span>
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs">
        <div><span className="stat-label">Stop Ticks</span><div className="font-mono mt-0.5">{rc.stop_distance_ticks}</div></div>
        <div><span className="stat-label">$/Lot Risk</span><div className="font-mono mt-0.5">${rc.dollar_risk_per_lot.toFixed(2)}</div></div>
        <div><span className="stat-label">Max Lots</span><div className="font-mono mt-0.5">{rc.max_lots}</div></div>
        <div><span className="stat-label">Total Risk</span><div className="font-mono text-terminal-danger mt-0.5">${rc.total_risk.toFixed(2)}</div></div>
        <div><span className="stat-label">Commission</span><div className="font-mono mt-0.5">${rc.total_commission.toFixed(2)}</div></div>
        <div><span className="stat-label">Slippage</span><div className="font-mono mt-0.5">${rc.total_slippage.toFixed(2)}</div></div>
        <div><span className="stat-label">Round-Trip</span><div className="font-mono mt-0.5">${rc.round_trip_cost.toFixed(2)}</div></div>
        <div><span className="stat-label">R:R Ratio</span><div className="font-mono text-terminal-success mt-0.5">{rc.risk_reward_ratio?.toFixed(2) ?? '—'}</div></div>
      </div>

      {rc.caution_flags.length > 0 && (
        <div className="pt-2 border-t border-terminal-border/50">
          <span className="stat-label text-terminal-warning">Caution Flags</span>
          {rc.caution_flags.map((f, i) => <div key={i} className="text-[10px] text-terminal-warning mt-1">⚠ {f}</div>)}
        </div>
      )}

      {lp && lp.entry_levels.length > 0 && (
        <div className="pt-2 border-t border-terminal-border/50">
          <span className="stat-label">Entry Ladder</span>
          <div className="mt-1 space-y-1">
            {lp.entry_levels.map(l => (
              <div key={l.level_index} className="flex justify-between text-[10px] font-mono">
                <span>{l.description}</span>
                <span className="text-terminal-text-dim">${l.dollar_risk.toFixed(0)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {lp && lp.target_levels.length > 0 && (
        <div className="pt-2 border-t border-terminal-border/50">
          <span className="stat-label">Target Ladder</span>
          <div className="mt-1 space-y-1">
            {lp.target_levels.map(l => (
              <div key={l.level_index} className="flex justify-between text-[10px] font-mono">
                <span>{l.description}</span>
                <span className="text-terminal-success">{l.lots} lots</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
