"""In-memory cache manager for market data, indicators, regime, and account state."""
from datetime import datetime
from typing import Any, Optional

from app.contracts.indicators import IndicatorSet
from app.contracts.market_data import MarketSnapshot, OHLCVSeries, SpreadQuote
from app.contracts.regime import MacroBias, RegimeState, RegimeType
from app.contracts.signals import SignalCard
from app.core.logging import get_logger
from app.config.loader import load_strategy_settings

logger = get_logger(__name__)


class CacheManager:
    """Centralized in-memory cache for the platform."""

    _instance: Optional["CacheManager"] = None

    def __new__(cls) -> "CacheManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        # Market data caches
        self._ohlcv_cache: dict[str, OHLCVSeries] = {}
        self._latest_snapshots: dict[str, MarketSnapshot] = {}
        self._spread_cache: dict[str, SpreadQuote] = {}

        # Indicator cache
        self._indicator_cache: dict[str, IndicatorSet] = {}

        # Signal cache
        self._signal_cache: dict[str, SignalCard] = {}

        # Regime cache
        self._regime_cache: RegimeState = RegimeState()

        # Account cache
        risk_config = load_strategy_settings().get("risk", {})
        self._account_cache: dict[str, Any] = {
            "max_position_lots": risk_config.get("max_position_lots", 100),
            "max_risk_per_trade_usd": risk_config.get("max_risk_per_trade_usd", 50000.0),
            "max_daily_risk_usd": risk_config.get("max_daily_risk_usd", 200000.0),
            "default_slippage_ticks": risk_config.get("default_slippage_ticks", 1),
            "default_commission_per_lot": risk_config.get("default_commission_per_lot", 2.50),
        }

    # --- OHLCV ---

    def cache_key(self, symbol: str, timeframe: str) -> str:
        return f"{symbol}:{timeframe}"

    def set_ohlcv(self, symbol: str, timeframe: str, series: OHLCVSeries) -> None:
        key = self.cache_key(symbol, timeframe)
        self._ohlcv_cache[key] = series
        if series.latest:
            bar = series.latest
            self._latest_snapshots[symbol] = MarketSnapshot(
                symbol=symbol,
                product_key=series.product_key,
                last_price=bar.close,
                volume=bar.volume,
                timestamp=bar.timestamp,
            )
        logger.info("ohlcv_cached", symbol=symbol, timeframe=timeframe, bars=series.length)

    def get_ohlcv(self, symbol: str, timeframe: str) -> Optional[OHLCVSeries]:
        return self._ohlcv_cache.get(self.cache_key(symbol, timeframe))

    def get_snapshot(self, symbol: str) -> Optional[MarketSnapshot]:
        return self._latest_snapshots.get(symbol)

    def get_all_snapshots(self) -> dict[str, MarketSnapshot]:
        return dict(self._latest_snapshots)

    # --- Spreads ---

    def set_spread(self, spread_symbol: str, quote: SpreadQuote) -> None:
        self._spread_cache[spread_symbol] = quote

    def get_spread(self, spread_symbol: str) -> Optional[SpreadQuote]:
        return self._spread_cache.get(spread_symbol)

    def get_all_spreads(self) -> dict[str, SpreadQuote]:
        return dict(self._spread_cache)

    # --- Indicators ---

    def set_indicators(self, symbol: str, timeframe: str, indicators: IndicatorSet) -> None:
        key = self.cache_key(symbol, timeframe)
        self._indicator_cache[key] = indicators

    def get_indicators(self, symbol: str, timeframe: str) -> Optional[IndicatorSet]:
        return self._indicator_cache.get(self.cache_key(symbol, timeframe))

    # --- Signals ---

    def set_signal_card(self, symbol: str, card: SignalCard) -> None:
        self._signal_cache[symbol] = card

    def get_signal_card(self, symbol: str) -> Optional[SignalCard]:
        return self._signal_cache.get(symbol)

    def get_all_signal_cards(self) -> dict[str, SignalCard]:
        return dict(self._signal_cache)

    # --- Regime ---

    def set_regime(self, regime: RegimeType, macro_bias: MacroBias, notes: str = "") -> RegimeState:
        self._regime_cache = RegimeState(
            regime=regime,
            macro_bias=macro_bias,
            notes=notes,
            updated_at=datetime.utcnow(),
        )
        return self._regime_cache

    def get_regime(self) -> RegimeState:
        return self._regime_cache

    # --- Account ---

    def update_account(self, updates: dict[str, Any]) -> dict[str, Any]:
        for key, value in updates.items():
            if value is not None and key in self._account_cache:
                self._account_cache[key] = value
        return dict(self._account_cache)

    def get_account(self) -> dict[str, Any]:
        return dict(self._account_cache)

    # --- Reset ---

    def clear_all(self) -> None:
        self._ohlcv_cache.clear()
        self._latest_snapshots.clear()
        self._spread_cache.clear()
        self._indicator_cache.clear()
        self._signal_cache.clear()
