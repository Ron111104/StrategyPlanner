import { create } from 'zustand'
import type { Timeframe, StrategySignal, RegimeState, AccountConfig, ContractsResponse } from '../types'

interface AppStore {
  // Selected state
  selectedProduct: string
  selectedTimeframe: Timeframe
  setSelectedProduct: (p: string) => void
  setSelectedTimeframe: (t: Timeframe) => void

  // Regime
  regime: RegimeState | null
  setRegime: (r: RegimeState) => void

  // Signals
  signals: StrategySignal[]
  setSignals: (s: StrategySignal[]) => void
  selectedSignal: StrategySignal | null
  setSelectedSignal: (s: StrategySignal | null) => void

  // Contracts
  contracts: ContractsResponse | null
  setContracts: (c: ContractsResponse) => void

  // Account
  accountConfig: AccountConfig | null
  setAccountConfig: (a: AccountConfig) => void

  // UI
  sidebarOpen: boolean
  toggleSidebar: () => void
  activePanel: string
  setActivePanel: (p: string) => void
}

export const useAppStore = create<AppStore>((set) => ({
  selectedProduct: 'FFN26',
  selectedTimeframe: '1H',
  setSelectedProduct: (p) => set({ selectedProduct: p }),
  setSelectedTimeframe: (t) => set({ selectedTimeframe: t }),

  regime: null,
  setRegime: (r) => set({ regime: r }),

  signals: [],
  setSignals: (s) => set({ signals: s }),
  selectedSignal: null,
  setSelectedSignal: (s) => set({ selectedSignal: s }),

  contracts: null,
  setContracts: (c) => set({ contracts: c }),

  accountConfig: null,
  setAccountConfig: (a) => set({ accountConfig: a }),

  sidebarOpen: true,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  activePanel: 'dashboard',
  setActivePanel: (p) => set({ activePanel: p }),
}))
