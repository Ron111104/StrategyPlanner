// ── Domain Types ─────────────────────────────────────
export type Timeframe = '1M' | '5M' | '15M' | '1H' | '4H' | '1D'
export type ContractType = 'outright' | 'spread'
export type MarketRegime = 'event' | 'volatility' | 'trend' | 'range' | 'no_signal'
export type MacroBias = 'hawkish' | 'dovish' | 'neutral'
export type SignalDirection = 'long' | 'short' | 'neutral'

export interface OHLCVBar { timestamp: string; open: number; high: number; low: number; close: number; volume: number; timeframe: Timeframe; product: string }
export interface SpreadBar { timestamp: string; open_bp: number; high_bp: number; low_bp: number; close_bp: number; volume: number; timeframe: Timeframe; product: string; front_contract: string; back_contract: string }
export interface MarketSnapshot { timestamp: string; front_contract: string; back_contract: string; front_price: number; back_price: number; spread_bp: number; front_volume: number; back_volume: number; timeframe: Timeframe }

export interface RegimeState { regime: MarketRegime; macro_bias: MacroBias; confidence: number; is_manual_override: boolean; override_expiration: string | null; active_events: MacroEvent[]; event_lock_active: boolean; volatility_level: number; classified_at: string; classification_reason: string }
export interface MacroEvent { event_id: string; name: string; scheduled_time: string; impact: string; description?: string; lock_window_hours: number }
export interface RegimeUpdateRequest { regime?: MarketRegime; macro_bias?: MacroBias; override_expiration_hours?: number; force_event_lock?: boolean; volatility_override?: number }

export interface ScaleLevel { level_index: number; price: number; lots: number; ratio: number; dollar_risk: number; description: string }
export interface LadderPlan { entry_levels: ScaleLevel[]; target_levels: ScaleLevel[]; stop_price: number; total_lots: number; total_risk: number; average_entry: number; risk_reward_ratio: number | null }
export interface RiskCalcResult { stop_distance_ticks: number; stop_distance_price: number; dollar_risk_per_lot: number; max_lots: number; total_risk: number; commission_per_lot: number; total_commission: number; slippage_per_lot: number; total_slippage: number; round_trip_cost: number; risk_reward_ratio: number | null; effective_max_risk: number; event_adjusted: boolean; caution_flags: string[] }

export interface StrategySignal { signal_id: string; strategy_name: string; product: string; contract_type: ContractType; timeframe: Timeframe; generated_at: string; direction: SignalDirection; entry_price: number; stop_price: number; targets: number[]; risk_calc: RiskCalcResult; ladder_plan: LadderPlan | null; confidence_score: number; priority: number; caution_flag: boolean; caution_reasons: string[]; trigger_conditions: string[]; disable_conditions_checked: string[]; invalidation_conditions: string[]; regime_context: RegimeState; macro_bias: MacroBias; strategy_metadata: Record<string, unknown> }
export interface NoSignalResponse { product: string; timeframe: Timeframe; reason: string; regime: MarketRegime; macro_bias: MacroBias; checks_performed: string[] }
export interface StrategyEvaluateResponse { product: string; timeframe: Timeframe; regime: RegimeState; signals: StrategySignal[]; no_signal_reasons: NoSignalResponse[]; evaluation_time_ms: number; strategies_evaluated: string[]; conflicting_strategies: string[]; timestamp: string }

export interface AccountConfig { max_risk_per_trade: number; max_lots: number; max_daily_risk: number; event_risk_multiplier: number; default_slippage_ticks: number; default_commission_per_lot: number }
export interface OutrightContract { symbol: string; type: 'outright'; description: string; tick_size: number; tick_value: number; contract_value: number; expiry?: string }
export interface SpreadContract { symbol: string; type: 'spread'; description: string; front_contract: string; back_contract: string; tick_size_bp: number; tick_value: number }
export interface ContractsResponse { outrights: OutrightContract[]; spreads: SpreadContract[]; total_count: number }
export interface StrategyDefinition { name: string; regimes: string[]; contract_types: string[]; priority: number; risk_multiplier: number; volatility_suitability: string; description: string }
