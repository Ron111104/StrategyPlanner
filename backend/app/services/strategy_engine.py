"""
Strategy Engine.

Orchestrates strategy evaluation by coordinating indicator computation,
regime classification, risk profiling, and signal generation across
all configured strategy definitions.
"""

from __future__ import annotations

import time
from typing import Any

from app.config.settings import ContractRegistry
from app.contracts.engine_output import (
    NoSignalResponse,
    SignalDirection,
    SignalStrength,
    StrategyEvaluateRequest,
    StrategyEvaluateResponse,
    StrategySignal,
)
from app.contracts.execution_inputs import AccountConfig
from app.contracts.macro_inputs import MacroBias, MarketRegime, RegimeState
from app.contracts.market_data import OHLCVBar
from app.core.exceptions import InsufficientDataError, InvalidContractError
from app.core.logging import get_logger
from app.services.data_provider import DataProvider
from app.services.indicator_engine import IndicatorEngine
from app.services.regime_engine import RegimeEngine
from app.services.risk_engine import RiskEngine
from app.strategies.definitions import (
    CurveFlattener,
    CurveSteepener,
    EventFade,
    EventMomentum,
    MeanReversionRange,
    StrategyDefinition,
    TrendFedRepricing,
    VolatilityFade,
)
from app.utils.datetime_helpers import now_utc
from app.utils.math_helpers import round_to_tick, safe_divide
from app.utils.validation_helpers import validate_bars_minimum

logger = get_logger(__name__)

_DEFAULT_ACCOUNT = AccountConfig(
    account_size_usd=100_000.0,
    risk_per_trade_usd=500.0,
    max_risk_per_trade_usd=2000.0,
    max_position_size=50,
    slippage_ticks=1,
    commission_per_side=2.50,
    event_risk_reduction=0.5,
)


class StrategyEngine:
    """
    Orchestrates evaluation of all strategy definitions against current
    market data, indicators, and regime state.
    """

    def __init__(
        self,
        indicator_engine: IndicatorEngine,
        risk_engine: RiskEngine,
        regime_engine: RegimeEngine,
        data_provider: DataProvider,
        contract_registry: ContractRegistry,
        config: dict[str, Any] | None = None,
    ) -> None:
        self._indicator_engine = indicator_engine
        self._risk_engine = risk_engine
        self._regime_engine = regime_engine
        self._data_provider = data_provider
        self._contract_registry = contract_registry
        self._config = config or {}

        self._min_bars = self._config.get("min_bars_required", 51)
        self._confidence_threshold = self._config.get("confidence_threshold", 0.6)
        self._max_signals = self._config.get("max_simultaneous_signals", 5)

        self._strategies: list[StrategyDefinition] = self._load_strategies()
        self._latest_signals: dict[str, StrategySignal | NoSignalResponse] = {}

        logger.info(
            "strategy_engine_init",
            strategies_loaded=len(self._strategies),
            min_bars=self._min_bars,
        )

    def _load_strategies(self) -> list[StrategyDefinition]:
        """Load and sort all strategy definitions by priority."""
        strategies = [
            TrendFedRepricing(),
            MeanReversionRange(),
            EventMomentum(),
            EventFade(),
            VolatilityFade(),
            CurveSteepener(),
            CurveFlattener(),
        ]
        strategies.sort(key=lambda s: s.priority)
        return strategies

    async def evaluate(
        self,
        request: StrategyEvaluateRequest,
    ) -> StrategyEvaluateResponse:
        """
        Evaluate all applicable strategies for a given product and timeframe.

        1. Fetch bars from data provider cache
        2. Validate minimum bar count
        3. Compute all indicators
        4. Classify or override regime
        5. Evaluate each strategy
        6. Compute risk profiles for signals
        7. Sort by confidence and return
        """
        start_time = time.perf_counter()
        product = request.product
        timeframe = request.timeframe.value if hasattr(request.timeframe, 'value') else str(request.timeframe)

        logger.info("strategy_evaluate_start", product=product, timeframe=timeframe)

        # 1. Get bars
        bars = await self._data_provider.get_bars(product, timeframe)
        if bars is None or len(bars) == 0:
            # Try fetching
            try:
                bars = await self._data_provider.fetch_bars(product, timeframe)
            except Exception as exc:
                logger.error("data_fetch_failed", product=product, error=str(exc))
                bars = []

        if not bars:
            elapsed = (time.perf_counter() - start_time) * 1000
            no_signal = NoSignalResponse(
                product=product,
                reason="No market data available",
                regime=MarketRegime.RANGE,
                bias=MacroBias.NEUTRAL,
                timestamp=now_utc(),
                strategies_evaluated=[],
            )
            self._latest_signals[product] = no_signal
            return StrategyEvaluateResponse(
                product=product,
                timeframe=request.timeframe,
                signals=[],
                no_signal_reasons=[no_signal],
                regime=RegimeState(
                    current_regime=MarketRegime.RANGE,
                    macro_bias=MacroBias.NEUTRAL,
                    confidence=0.0,
                    source="default",
                    updated_at=now_utc(),
                ),
                evaluation_time_ms=elapsed,
                bars_analyzed=0,
                timestamp=now_utc(),
            )

        # 2. Validate minimum bars
        try:
            validate_bars_minimum(bars, self._min_bars, f"strategy evaluation for {product}")
        except ValueError:
            elapsed = (time.perf_counter() - start_time) * 1000
            no_signal = NoSignalResponse(
                product=product,
                reason=f"Insufficient data: {len(bars)} bars < {self._min_bars} minimum",
                regime=MarketRegime.RANGE,
                bias=MacroBias.NEUTRAL,
                timestamp=now_utc(),
                strategies_evaluated=[],
            )
            self._latest_signals[product] = no_signal
            return StrategyEvaluateResponse(
                product=product,
                timeframe=request.timeframe,
                signals=[],
                no_signal_reasons=[no_signal],
                regime=RegimeState(
                    current_regime=MarketRegime.RANGE,
                    macro_bias=MacroBias.NEUTRAL,
                    confidence=0.0,
                    source="default",
                    updated_at=now_utc(),
                ),
                evaluation_time_ms=elapsed,
                bars_analyzed=len(bars),
                timestamp=now_utc(),
            )

        # 3. Compute indicators
        indicators = self._indicator_engine.compute_all(bars, self._indicator_engine._config)

        # 4. Classify regime (or use override)
        if request.regime_override:
            regime = RegimeState(
                current_regime=request.regime_override,
                macro_bias=request.bias_override or MacroBias.NEUTRAL,
                confidence=1.0,
                source="manual",
                updated_at=now_utc(),
            )
        else:
            regime = await self._regime_engine.classify_regime(
                product=product,
                bars=bars,
                indicators=indicators,
            )

        if request.bias_override:
            regime.macro_bias = request.bias_override

        # 5. Get account config
        account = request.account_config or _DEFAULT_ACCOUNT

        # Determine product type
        is_spread = self._is_spread_product(product)
        product_type = "spread" if is_spread else "outright"

        # Get contract specs
        tick_size, tick_value = self._get_contract_specs(product, is_spread)

        # 6. Evaluate each strategy
        signals: list[StrategySignal] = []
        no_signal_reasons: list[NoSignalResponse] = []

        for strategy in self._strategies:
            try:
                signal = self._evaluate_strategy(
                    strategy=strategy,
                    bars=bars,
                    indicators=indicators,
                    regime=regime,
                    account=account,
                    product=product,
                    product_type=product_type,
                    tick_size=tick_size,
                    tick_value=tick_value,
                    is_spread=is_spread,
                )

                if signal is not None:
                    signals.append(signal)
                else:
                    no_signal_reasons.append(
                        NoSignalResponse(
                            product=product,
                            reason=f"{strategy.name}: No entry conditions met for {regime.current_regime.value} regime",
                            regime=regime.current_regime,
                            bias=regime.macro_bias,
                            timestamp=now_utc(),
                            strategies_evaluated=[strategy.name],
                        )
                    )
            except Exception as exc:
                logger.error(
                    "strategy_eval_error",
                    strategy=strategy.name,
                    product=product,
                    error=str(exc),
                )
                no_signal_reasons.append(
                    NoSignalResponse(
                        product=product,
                        reason=f"{strategy.name}: Evaluation error - {str(exc)}",
                        regime=regime.current_regime,
                        bias=regime.macro_bias,
                        timestamp=now_utc(),
                        strategies_evaluated=[strategy.name],
                    )
                )

        # 7. Sort signals by confidence, limit count
        signals.sort(key=lambda s: s.confidence, reverse=True)
        signals = signals[: self._max_signals]

        # Cache latest
        if signals:
            self._latest_signals[product] = signals[0]
        elif no_signal_reasons:
            self._latest_signals[product] = no_signal_reasons[0]

        elapsed = (time.perf_counter() - start_time) * 1000

        logger.info(
            "strategy_evaluate_complete",
            product=product,
            signals=len(signals),
            elapsed_ms=f"{elapsed:.2f}",
        )

        return StrategyEvaluateResponse(
            product=product,
            timeframe=request.timeframe,
            signals=signals,
            no_signal_reasons=no_signal_reasons,
            regime=regime,
            evaluation_time_ms=round(elapsed, 2),
            bars_analyzed=len(bars),
            timestamp=now_utc(),
        )

    async def get_latest_signal(
        self,
        product: str,
    ) -> StrategySignal | NoSignalResponse:
        """Return the latest cached signal for a product."""
        cached = self._latest_signals.get(product)
        if cached is not None:
            return cached

        return NoSignalResponse(
            product=product,
            reason="No evaluation has been performed yet",
            regime=MarketRegime.RANGE,
            bias=MacroBias.NEUTRAL,
            timestamp=now_utc(),
            strategies_evaluated=[],
        )

    def get_strategy_list(self) -> list[dict[str, Any]]:
        """Return list of available strategies with metadata."""
        return [
            {
                "name": s.name,
                "description": s.description,
                "applicable_regimes": [r.value for r in s.applicable_regimes],
                "applicable_products": s.applicable_products,
                "priority": s.priority,
                "risk_multiplier": s.risk_multiplier,
            }
            for s in self._strategies
        ]

    def _evaluate_strategy(
        self,
        strategy: StrategyDefinition,
        bars: list[OHLCVBar],
        indicators: dict[str, Any],
        regime: RegimeState,
        account: AccountConfig,
        product: str,
        product_type: str,
        tick_size: float,
        tick_value: float,
        is_spread: bool,
    ) -> StrategySignal | None:
        """Evaluate a single strategy against current market conditions."""

        # Check regime applicability
        if regime.current_regime not in strategy.applicable_regimes:
            return None

        # Check product type applicability
        if product_type not in strategy.applicable_products:
            return None

        # Check disable conditions
        if strategy.should_disable(regime, indicators):
            return None

        # Evaluate entry conditions
        signal_params = strategy.evaluate(bars, indicators, regime)
        if signal_params is None:
            return None

        entry_price = signal_params["entry_price"]
        stop_price = signal_params["stop_price"]
        target_price = signal_params["target_price"]
        direction = signal_params["direction"]
        confidence = signal_params.get("confidence", 0.5)
        notes = signal_params.get("notes", [])
        invalidation = signal_params.get("invalidation_conditions", [])
        indicators_used = signal_params.get("indicators_used", {})

        # Skip low confidence signals
        if confidence < self._confidence_threshold:
            return None

        # Round prices to tick
        entry_price = round_to_tick(entry_price, tick_size)
        stop_price = round_to_tick(stop_price, tick_size)
        target_price = round_to_tick(target_price, tick_size)

        # Compute position size
        is_event = regime.current_regime == MarketRegime.EVENT
        from app.contracts.execution_inputs import PositionSizingRequest

        sizing_req = PositionSizingRequest(
            account_config=account,
            entry_price=entry_price,
            stop_price=stop_price,
            contract_tick_size=tick_size,
            contract_tick_value=tick_value,
            is_spread=is_spread,
            is_event_window=is_event,
        )
        position_size = self._risk_engine.compute_position_size(sizing_req)

        # Compute risk profile
        risk_profile = self._risk_engine.compute_risk_profile(
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            position_size=position_size,
            direction=direction,
            tick_size=tick_size,
            tick_value=tick_value,
            slippage_ticks=account.slippage_ticks,
            commission_per_side=account.commission_per_side,
        )

        # Generate ladder
        ladder = self._risk_engine.generate_ladder(
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            total_size=position_size,
            num_levels=3,
            tick_size=tick_size,
            direction=direction,
        )

        # Determine signal strength
        if confidence >= 0.8:
            strength = SignalStrength.STRONG
        elif confidence >= 0.6:
            strength = SignalStrength.MODERATE
        else:
            strength = SignalStrength.WEAK

        return StrategySignal(
            strategy_name=strategy.name,
            product=product,
            direction=SignalDirection(direction),
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            confidence=round(confidence, 4),
            strength=strength,
            regime=regime.current_regime,
            bias=regime.macro_bias,
            risk_reward_ratio=round(risk_profile.risk_reward_ratio, 2),
            dollar_risk=round(risk_profile.dollar_risk, 2),
            position_size=position_size,
            timestamp=now_utc(),
            invalidation_conditions=invalidation,
            notes=notes,
            ladder=ladder,
            indicators_used=indicators_used,
        )

    def _is_spread_product(self, product: str) -> bool:
        """Check if a product is a spread contract."""
        if "-" in product:
            return True
        for spread in self._contract_registry.spreads:
            if spread.symbol == product:
                return True
        return False

    def _get_contract_specs(
        self,
        product: str,
        is_spread: bool,
    ) -> tuple[float, float]:
        """Get tick_size and tick_value for a contract."""
        if is_spread:
            for spread in self._contract_registry.spreads:
                if spread.symbol == product:
                    return spread.tick_size_bp * 0.01, spread.tick_value
            # Default spread specs
            return 0.005, 20.835
        else:
            for outright in self._contract_registry.outrights:
                if outright.symbol == product:
                    return outright.tick_size, outright.tick_value
            # Default outright specs
            return 0.005, 20.835
