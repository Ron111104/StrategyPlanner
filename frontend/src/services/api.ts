import axios from 'axios'
import type { AccountConfig, ContractsResponse, RegimeState, RegimeUpdateRequest, StrategyEvaluateResponse, StrategyDefinition, Timeframe, MarketRegime, MacroBias } from '../types'

const api = axios.create({ baseURL: '/api', timeout: 30000, headers: { 'Content-Type': 'application/json' } })

// ── Market Data ──────────────────────────────────────
export const fetchMarketData = async (products: string[], timeframe: Timeframe) => {
  const { data } = await api.post('/market-data/fetch', { products, timeframe })
  return data
}
export const getContracts = async (): Promise<ContractsResponse> => {
  const { data } = await api.get('/market-data/contracts')
  return data
}
export const getSnapshots = async () => {
  const { data } = await api.get('/market-data/snapshots')
  return data
}
export const getCacheSummary = async () => {
  const { data } = await api.get('/market-data/cache')
  return data
}

// ── Strategy ─────────────────────────────────────────
export const evaluateStrategies = async (product: string, timeframe: Timeframe, strategies?: string[], regime_override?: MarketRegime, macro_bias_override?: MacroBias): Promise<StrategyEvaluateResponse> => {
  const { data } = await api.post('/strategy/evaluate', { product, timeframe, strategies, regime_override, macro_bias_override })
  return data
}
export const getBestSignal = async (product: string) => {
  const { data } = await api.get('/strategy/signal', { params: { product } })
  return data
}
export const getStrategyDefinitions = async (): Promise<{ strategies: StrategyDefinition[] }> => {
  const { data } = await api.get('/strategy/definitions')
  return data
}

// ── Regime ───────────────────────────────────────────
export const getCurrentRegime = async (): Promise<RegimeState> => {
  const { data } = await api.get('/regime/current')
  return data
}
export const updateRegime = async (request: RegimeUpdateRequest): Promise<RegimeState> => {
  const { data } = await api.put('/regime/update', request)
  return data
}

// ── Account ──────────────────────────────────────────
export const getAccountConfig = async (): Promise<AccountConfig> => {
  const { data } = await api.get('/account/config')
  return data
}
export const updateAccountConfig = async (config: AccountConfig): Promise<AccountConfig> => {
  const { data } = await api.put('/account/config', config)
  return data
}

// ── Health ───────────────────────────────────────────
export const healthCheck = async () => {
  const { data } = await axios.get('/health')
  return data
}
