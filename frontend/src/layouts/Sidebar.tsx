import { motion } from 'framer-motion'
import { useAppStore } from '../store/useAppStore'
import { BarChart3, Activity, Gauge, Target, Calendar, Settings, TrendingUp, Shield } from 'lucide-react'

const navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: BarChart3 },
  { id: 'strategies', label: 'Strategies', icon: Target },
  { id: 'signals', label: 'Signals', icon: TrendingUp },
  { id: 'risk', label: 'Risk', icon: Shield },
  { id: 'regime', label: 'Regime', icon: Activity },
  { id: 'events', label: 'Events', icon: Calendar },
  { id: 'settings', label: 'Settings', icon: Settings },
]

export default function Sidebar() {
  const { sidebarOpen, activePanel, setActivePanel } = useAppStore()

  return (
    <motion.aside
      animate={{ width: sidebarOpen ? 200 : 56 }}
      className="h-full bg-terminal-surface border-r border-terminal-border flex flex-col flex-shrink-0"
    >
      <div className="p-3 border-b border-terminal-border">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-gradient-to-br from-terminal-accent to-violet-500 flex items-center justify-center">
            <Gauge className="w-4 h-4 text-white" />
          </div>
          {sidebarOpen && <span className="font-semibold text-sm tracking-tight">ZQ Planner</span>}
        </div>
      </div>

      <nav className="flex-1 py-2 space-y-0.5 px-2">
        {navItems.map(item => {
          const Icon = item.icon
          const isActive = activePanel === item.id
          return (
            <button key={item.id} onClick={() => setActivePanel(item.id)}
              className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-md text-xs transition-all duration-150 ${isActive ? 'bg-terminal-accent/15 text-terminal-accent' : 'text-terminal-text-dim hover:text-terminal-text hover:bg-terminal-border/30'}`}>
              <Icon className="w-4 h-4 flex-shrink-0" />
              {sidebarOpen && <span className="truncate">{item.label}</span>}
            </button>
          )
        })}
      </nav>

      <div className="p-3 border-t border-terminal-border">
        <div className={`flex items-center gap-2 ${sidebarOpen ? '' : 'justify-center'}`}>
          <div className="w-2 h-2 rounded-full bg-terminal-success animate-pulse-slow" />
          {sidebarOpen && <span className="text-[10px] text-terminal-text-dim">System Online</span>}
        </div>
      </div>
    </motion.aside>
  )
}
