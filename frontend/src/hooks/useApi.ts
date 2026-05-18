import { useQuery, useMutation } from '@tanstack/react-query'
import * as api from '../services/api'
import type { Timeframe, MarketRegime, MacroBias, RegimeUpdateRequest, AccountConfig } from '../types'

export const useContracts = () => useQuery({ queryKey: ['contracts'], queryFn: api.getContracts })
export const useSnapshots = () => useQuery({ queryKey: ['snapshots'], queryFn: api.getSnapshots, refetchInterval: 10000 })
export const useCacheSummary = () => useQuery({ queryKey: ['cache'], queryFn: api.getCacheSummary })
export const useRegime = () => useQuery({ queryKey: ['regime'], queryFn: api.getCurrentRegime, refetchInterval: 5000 })
export const useAccountConfig = () => useQuery({ queryKey: ['account'], queryFn: api.getAccountConfig })
export const useStrategyDefs = () => useQuery({ queryKey: ['strategyDefs'], queryFn: api.getStrategyDefinitions })
export const useHealth = () => useQuery({ queryKey: ['health'], queryFn: api.healthCheck, refetchInterval: 15000 })

export const useFetchMarketData = () => useMutation({ mutationFn: ({ products, timeframe }: { products: string[]; timeframe: Timeframe }) => api.fetchMarketData(products, timeframe) })
export const useEvaluateStrategies = () => useMutation({ mutationFn: ({ product, timeframe, strategies, regime_override, macro_bias_override }: { product: string; timeframe: Timeframe; strategies?: string[]; regime_override?: MarketRegime; macro_bias_override?: MacroBias }) => api.evaluateStrategies(product, timeframe, strategies, regime_override, macro_bias_override) })
export const useUpdateRegime = () => useMutation({ mutationFn: (req: RegimeUpdateRequest) => api.updateRegime(req) })
export const useUpdateAccount = () => useMutation({ mutationFn: (config: AccountConfig) => api.updateAccountConfig(config) })
