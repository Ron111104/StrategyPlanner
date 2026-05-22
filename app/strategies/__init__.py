from app.strategies.base import BaseStrategy
from app.strategies.trend_fed_repricing import TrendFedRepricing
from app.strategies.mean_reversion_range import MeanReversionRange
from app.strategies.event_momentum import EventMomentum
from app.strategies.event_fade import EventFade
from app.strategies.volatility_fade import VolatilityFade
from app.strategies.curve_steepener import CurveSteepener
from app.strategies.curve_flattener import CurveFlattener

STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    "trend_fed_repricing": TrendFedRepricing,
    "mean_reversion_range": MeanReversionRange,
    "event_momentum": EventMomentum,
    "event_fade": EventFade,
    "volatility_fade": VolatilityFade,
    "curve_steepener": CurveSteepener,
    "curve_flattener": CurveFlattener,
}

__all__ = [
    "BaseStrategy",
    "TrendFedRepricing",
    "MeanReversionRange",
    "EventMomentum",
    "EventFade",
    "VolatilityFade",
    "CurveSteepener",
    "CurveFlattener",
    "STRATEGY_REGISTRY",
]
