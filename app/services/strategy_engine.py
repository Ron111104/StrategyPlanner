"""Strategy evaluation engine coordinating all strategy instances."""
from typing import Optional

from app.config.loader import get_product_config, load_strategy_settings
from app.contracts.indicators import IndicatorSet
from app.contracts.market_data import OHLCVSeries
from app.contracts.regime import RegimeState
from app.contracts.signals import SignalCard, SignalDirection, StrategySignal
from app.contracts.strategy import EntryExitPlan, StrategyEvalResult
from app.core.logging import get_logger
from app.services.cache import CacheManager
from app.services.indicator_engine import IndicatorEngine
from app.services.regime_engine import RegimeEngine
from app.strategies import STRATEGY_REGISTRY
from app.strategies.base import BaseStrategy

logger = get_logger(__name__)


class StrategyEngine:
    """Orchestrates strategy evaluation across instruments."""

    def __init__(self) -> None:
        self._cache = CacheManager()
        self._indicator_engine = IndicatorEngine()
        self._regime_engine = RegimeEngine()
        self._strategy_settings = load_strategy_settings().get("strategies", {})
        self._strategies: dict[str, BaseStrategy] = {}
        self._init_strategies()

    def _init_strategies(self) -> None:
        """Initialize strategy instances from registry."""
        for name, cls in STRATEGY_REGISTRY.items():
            config = self._strategy_settings.get(name, {})
            if config.get("enabled", True):
                self._strategies[name] = cls()
                logger.info("strategy_loaded", name=name)
            else:
                logger.info("strategy_disabled", name=name)

    def evaluate(
        self,
        product_key: str,
        symbols: list[str],
        timeframe: str,
        strategy_names: Optional[list[str]] = None,
        regime_override: Optional[RegimeState] = None,
    ) -> list[StrategyEvalResult]:
        """Evaluate strategies for given symbols."""
        product_config = get_product_config(product_key)
        regime = regime_override or self._regime_engine.get_current_regime()
        results: list[StrategyEvalResult] = []

        strategies_to_run = self._strategies
        if strategy_names:
            strategies_to_run = {
                n: s for n, s in self._strategies.items() if n in strategy_names
            }

        for symbol in symbols:
            result = self._evaluate_symbol(
                symbol=symbol,
                product_key=product_key,
                product_config=product_config,
                timeframe=timeframe,
                regime=regime,
                strategies=strategies_to_run,
            )
            results.append(result)

        return results

    def _evaluate_symbol(
        self,
        symbol: str,
        product_key: str,
        product_config: dict,
        timeframe: str,
        regime: RegimeState,
        strategies: dict[str, BaseStrategy],
    ) -> StrategyEvalResult:
        """Evaluate all applicable strategies for a single symbol."""
        is_spread = "-" in symbol
        instrument_type = "spread" if is_spread else "outright"

        # Get or compute indicators
        series = self._cache.get_ohlcv(symbol, timeframe)
        indicators = self._cache.get_indicators(symbol, timeframe)

        if series and not indicators:
            try:
                indicators = self._indicator_engine.compute_all(series)
            except Exception as e:
                logger.error("indicator_compute_error", symbol=symbol, error=str(e))

        signals: list[StrategySignal] = []
        plans: list[EntryExitPlan] = []
        evaluated: list[str] = []
        skipped: list[str] = []

        for name, strategy in strategies.items():
            strat_config = self._strategy_settings.get(name, {})

            # Check spread_only flag
            if strat_config.get("spread_only", False) and not is_spread:
                skipped.append(f"{name}: spread_only strategy, symbol is outright")
                continue

            # Check regime/timeframe applicability
            applicable_regimes = strat_config.get("applicable_regimes", [])
            applicable_timeframes = strat_config.get("applicable_timeframes", [])

            if not self._regime_engine.is_strategy_applicable(
                applicable_regimes, applicable_timeframes, timeframe
            ):
                skipped.append(f"{name}: regime/timeframe mismatch")
                continue

            if not series or not indicators:
                skipped.append(f"{name}: no data for {symbol}")
                continue

            try:
                signal = strategy.evaluate(series, indicators, regime, product_config)
                evaluated.append(name)

                if signal:
                    min_conf = strat_config.get("min_confidence", 0.5)
                    if signal.confidence >= min_conf:
                        signals.append(signal)
                        plan = strategy.build_entry_exit_plan(
                            signal, series, indicators, product_config
                        )
                        if plan:
                            plans.append(plan)
                    else:
                        skipped.append(f"{name}: confidence {signal.confidence} < {min_conf}")
            except Exception as e:
                logger.error("strategy_eval_error", strategy=name, symbol=symbol, error=str(e))
                skipped.append(f"{name}: error — {str(e)}")

        # Sort by confidence desc, then priority
        signals.sort(key=lambda s: s.confidence, reverse=True)
        best = signals[0] if signals else None

        # Build signal card and cache
        card = SignalCard(
            symbol=symbol,
            product_key=product_key,
            instrument_type=instrument_type,
            signals=signals,
            best_signal=best,
            overall_direction=best.direction if best else SignalDirection.FLAT,
            overall_confidence=best.confidence if best else 0.0,
            last_price=series.bars[-1].close if series and series.bars else None,
            spread_bp=series.bars[-1].close if series and series.bars and is_spread else None,
        )
        self._cache.set_signal_card(symbol, card)

        return StrategyEvalResult(
            symbol=symbol,
            product_key=product_key,
            timeframe=timeframe,
            regime=regime.regime.value,
            macro_bias=regime.macro_bias.value,
            signals=signals,
            entry_exit_plans=plans,
            best_opportunity=best,
            evaluated_strategies=evaluated,
            skipped_strategies=skipped,
        )

    def get_all_signal_cards(self) -> list[SignalCard]:
        """Return all cached signal cards."""
        return list(self._cache.get_all_signal_cards().values())
