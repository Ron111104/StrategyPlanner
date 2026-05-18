"""
Strategy Engine — multi-strategy evaluation, conflict resolution, and signal generation.

Orchestrates all strategy definitions against market data and regime state.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional

from app.contracts.engine_output import (
    NoSignalResponse,
    SignalDirection,
    StrategyEvaluateRequest,
    StrategyEvaluateResponse,
    StrategySignal,
)
from app.contracts.execution_inputs import RiskCalcInput
from app.contracts.macro_inputs import MarketRegime, RegimeClassificationInput, RegimeState
from app.contracts.market_data import ContractType, OHLCVBar, SpreadBar, Timeframe
from app.core.logging import get_logger
from app.services.indicator_engine import IndicatorEngine, IndicatorResult
from app.services.regime_engine import RegimeEngine
from app.services.risk_engine import RiskEngine
from app.strategies.definitions import (
    STRATEGY_EVALUATORS,
    STRATEGY_REGISTRY,
    StrategyDefinition,
    StrategyEvaluation,
    StrategyName,
)

logger = get_logger(__name__)


class StrategyEngine:
    """
    Multi-strategy evaluation engine with conflict resolution and signal ranking.

    Supports:
    - evaluate_strategy: single strategy evaluation
    - evaluate_all: multi-strategy evaluation
    - select_strategy: best signal selection
    - build_signal: complete signal construction
    """

    def __init__(
        self,
        indicator_engine: IndicatorEngine,
        regime_engine: RegimeEngine,
        risk_engine: RiskEngine,
        settings: dict[str, Any],
    ) -> None:
        self._indicators = indicator_engine
        self._regime = regime_engine
        self._risk = risk_engine

        scoring_cfg = settings.get("scoring", {})
        self._min_confidence = scoring_cfg.get("min_confidence_threshold", 0.3)
        self._high_confidence = scoring_cfg.get("high_confidence_threshold", 0.7)
        self._caution_threshold = scoring_cfg.get("caution_threshold", 0.5)
        self._conflict_penalty = scoring_cfg.get("conflicting_strategy_penalty", 0.15)

        logger.info("strategy_engine_initialized")

    def evaluate_strategy(
        self,
        strategy_name: StrategyName,
        bars: list[OHLCVBar],
        spread_bars: list[SpreadBar] | None = None,
        product: str = "",
        contract_type: ContractType = ContractType.OUTRIGHT,
        regime_state: RegimeState | None = None,
    ) -> StrategyEvaluation:
        """Evaluate a single strategy against market data."""
        definition = STRATEGY_REGISTRY.get(strategy_name)
        if not definition:
            return StrategyEvaluation(
                strategy_name=strategy_name.value,
                disable_conditions=[f"Unknown strategy: {strategy_name}"],
            )

        # Check regime applicability
        if regime_state and regime_state.regime not in definition.regime_applicability:
            return StrategyEvaluation(
                strategy_name=strategy_name.value,
                disable_conditions=[
                    f"Regime {regime_state.regime.value} not applicable for {strategy_name.value}"
                ],
            )

        # Check contract type
        if contract_type not in definition.contract_types:
            return StrategyEvaluation(
                strategy_name=strategy_name.value,
                disable_conditions=[
                    f"Contract type {contract_type.value} not supported by {strategy_name.value}"
                ],
            )

        # Compute indicators
        if contract_type == ContractType.SPREAD and spread_bars:
            indicators = self._indicators.compute_spread_indicators(spread_bars, product)
            price = spread_bars[-1].close_bp if spread_bars else 0.0
        else:
            indicators = self._indicators.compute(bars, product)
            price = bars[-1].close if bars else 0.0

        if not indicators.is_valid:
            return StrategyEvaluation(
                strategy_name=strategy_name.value,
                disable_conditions=[indicators.error or "Invalid indicators"],
            )

        atr = indicators.current_atr

        # Run strategy evaluator
        evaluator = STRATEGY_EVALUATORS.get(strategy_name)
        if not evaluator:
            return StrategyEvaluation(
                strategy_name=strategy_name.value,
                disable_conditions=["No evaluator registered"],
            )

        if strategy_name in (StrategyName.CURVE_STEEPENER, StrategyName.CURVE_FLATTENER):
            return evaluator(indicators, price, atr)
        else:
            return evaluator(indicators, price, atr)

    def evaluate_all(
        self,
        bars: list[OHLCVBar],
        spread_bars: list[SpreadBar] | None = None,
        product: str = "",
        contract_type: ContractType = ContractType.OUTRIGHT,
        timeframe: Timeframe = Timeframe.H1,
        regime_override: MarketRegime | None = None,
        strategy_filter: list[str] | None = None,
    ) -> StrategyEvaluateResponse:
        """
        Evaluate all applicable strategies and return ranked signals.

        Handles conflict resolution, confidence ranking, and caution flags.
        """
        start = time.perf_counter()

        # Determine regime
        if regime_override:
            regime_state = RegimeState(regime=regime_override)
        else:
            # Auto-classify regime from indicators
            if bars:
                indicators = self._indicators.compute(bars, product)
                if indicators.is_valid and indicators.sma_fast and indicators.sma_slow:
                    regime_input = RegimeClassificationInput(
                        current_atr=indicators.current_atr,
                        atr_percentile=indicators.atr_percentile,
                        ma_fast=indicators.sma_fast[-1],
                        ma_slow=indicators.sma_slow[-1],
                        price=bars[-1].close,
                        donchian_upper=indicators.current_donchian_upper,
                        donchian_lower=indicators.current_donchian_lower,
                        dcw=indicators.current_dcw,
                        volume=bars[-1].volume,
                    )
                    regime_state = self._regime.classify(regime_input)
                else:
                    regime_state = self._regime.current_state
            else:
                regime_state = self._regime.current_state

        # Filter strategies
        strategies_to_evaluate = list(STRATEGY_REGISTRY.keys())
        if strategy_filter:
            strategies_to_evaluate = [
                s for s in strategies_to_evaluate
                if s.value in strategy_filter
            ]

        # Evaluate each strategy
        evaluations: list[tuple[StrategyName, StrategyEvaluation]] = []
        no_signal_reasons: list[NoSignalResponse] = []

        for strategy_name in strategies_to_evaluate:
            eval_result = self.evaluate_strategy(
                strategy_name=strategy_name,
                bars=bars,
                spread_bars=spread_bars,
                product=product,
                contract_type=contract_type,
                regime_state=regime_state,
            )

            if eval_result.is_applicable:
                evaluations.append((strategy_name, eval_result))
            else:
                reasons = eval_result.disable_conditions or ["No signal conditions met"]
                no_signal_reasons.append(NoSignalResponse(
                    product=product,
                    timeframe=timeframe,
                    reason="; ".join(reasons),
                    regime=regime_state.regime,
                    macro_bias=regime_state.macro_bias,
                    checks_performed=eval_result.trigger_conditions,
                ))

        # Detect conflicts
        conflicting = self._detect_conflicts(evaluations)

        # Build signals with risk
        signals: list[StrategySignal] = []
        for strategy_name, eval_result in evaluations:
            definition = STRATEGY_REGISTRY[strategy_name]
            tick_size = 0.005 if contract_type == ContractType.OUTRIGHT else 0.005
            tick_value = 20.835

            signal = self._build_signal(
                eval_result=eval_result,
                definition=definition,
                product=product,
                contract_type=contract_type,
                timeframe=timeframe,
                regime_state=regime_state,
                tick_size=tick_size,
                tick_value=tick_value,
                has_conflicts=strategy_name.value in conflicting,
            )
            if signal:
                signals.append(signal)

        # Sort by confidence (descending) then priority (ascending)
        signals.sort(key=lambda s: (-s.confidence_score, s.priority))

        elapsed = (time.perf_counter() - start) * 1000

        return StrategyEvaluateResponse(
            product=product,
            timeframe=timeframe,
            regime=regime_state,
            signals=signals,
            no_signal_reasons=no_signal_reasons,
            evaluation_time_ms=round(elapsed, 2),
            strategies_evaluated=[s.value for s in strategies_to_evaluate],
            conflicting_strategies=conflicting,
        )

    def select_strategy(
        self,
        response: StrategyEvaluateResponse,
    ) -> StrategySignal | None:
        """Select the best signal from evaluation response."""
        valid = [s for s in response.signals if s.confidence_score >= self._min_confidence]
        return valid[0] if valid else None

    def _build_signal(
        self,
        eval_result: StrategyEvaluation,
        definition: StrategyDefinition,
        product: str,
        contract_type: ContractType,
        timeframe: Timeframe,
        regime_state: RegimeState,
        tick_size: float,
        tick_value: float,
        has_conflicts: bool,
    ) -> StrategySignal | None:
        """Build a complete StrategySignal from evaluation result."""
        if not eval_result.is_applicable or eval_result.entry_price <= 0:
            return None

        # Compute risk
        risk_input = RiskCalcInput(
            entry_price=eval_result.entry_price,
            stop_price=eval_result.stop_price,
            contract_type=contract_type,
            tick_size=tick_size,
            tick_value=tick_value,
            is_event_regime=regime_state.regime == MarketRegime.EVENT,
            volatility_multiplier=definition.risk_multiplier,
        )
        risk_calc = self._risk.compute_risk(risk_input, eval_result.targets)

        # Build ladder
        direction = eval_result.direction
        ladder = self._risk.build_ladder(
            entry_price=eval_result.entry_price,
            stop_price=eval_result.stop_price,
            targets=eval_result.targets,
            total_lots=risk_calc.max_lots,
            tick_size=tick_size,
            tick_value=tick_value,
            direction=direction,
        )

        # Confidence adjustments
        confidence = eval_result.confidence
        if has_conflicts:
            confidence = max(0, confidence - self._conflict_penalty)

        # Caution flag
        caution = confidence < self._caution_threshold
        caution_reasons = list(eval_result.caution_reasons)
        if has_conflicts:
            caution_reasons.append("Conflicting strategy signals detected")
        if risk_calc.max_lots == 0:
            caution = True
            caution_reasons.append("Zero position size")

        # Direction
        sig_direction = {
            "long": SignalDirection.LONG,
            "short": SignalDirection.SHORT,
        }.get(direction, SignalDirection.NEUTRAL)

        return StrategySignal(
            signal_id=str(uuid.uuid4()),
            strategy_name=eval_result.strategy_name,
            product=product,
            contract_type=contract_type,
            timeframe=timeframe,
            direction=sig_direction,
            entry_price=eval_result.entry_price,
            stop_price=eval_result.stop_price,
            targets=eval_result.targets,
            risk_calc=risk_calc,
            ladder_plan=ladder,
            confidence_score=round(confidence, 3),
            priority=definition.priority,
            caution_flag=caution,
            caution_reasons=caution_reasons,
            trigger_conditions=eval_result.trigger_conditions,
            disable_conditions_checked=eval_result.disable_conditions,
            invalidation_conditions=eval_result.invalidation_conditions,
            regime_context=regime_state,
            macro_bias=regime_state.macro_bias,
            strategy_metadata=eval_result.metadata,
        )

    def _detect_conflicts(
        self,
        evaluations: list[tuple[StrategyName, StrategyEvaluation]],
    ) -> list[str]:
        """Detect conflicting strategy signals (opposing directions)."""
        directions: dict[str, list[str]] = {}
        for name, eval_result in evaluations:
            if eval_result.is_applicable:
                directions.setdefault(eval_result.direction, []).append(name.value)

        conflicting: list[str] = []
        if "long" in directions and "short" in directions:
            conflicting.extend(directions["long"])
            conflicting.extend(directions["short"])

        return conflicting
