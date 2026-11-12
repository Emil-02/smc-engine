"""Smart Money Concepts (ICT) detection for OHLC data.

>>> import smc_engine as smc
>>> result = smc.analyze(df, symbol="XAUUSD", timeframe="M15")
>>> result.zones_frame()
"""

from ._frame import prepare
from .engine import (
    Analysis,
    SMCConfig,
    analyze,
    detect_ltf_choch,
    htf_aligned,
    score_zone,
)
from .indicators import atr, ema_bias, rsi, trading_session
from .liquidity import build_liquidity_map, has_inducement, recent_sweep
from .models import (
    Direction,
    LiquidityPool,
    StructureBreak,
    StructureEvent,
    SwingKind,
    SwingPoint,
    Zone,
    ZoneKind,
)
from .structure import dealing_range, detect_structure
from .swings import find_swings
from .zones import (
    detect_breakers,
    detect_fvg,
    detect_order_blocks,
    price_position,
    price_position_label,
    tag_premium_discount,
    update_zone_lifecycle,
)

__version__ = "0.1.0"

__all__ = [
    "Analysis",
    "Direction",
    "LiquidityPool",
    "SMCConfig",
    "StructureBreak",
    "StructureEvent",
    "SwingKind",
    "SwingPoint",
    "Zone",
    "ZoneKind",
    "analyze",
    "atr",
    "build_liquidity_map",
    "dealing_range",
    "detect_breakers",
    "detect_fvg",
    "detect_ltf_choch",
    "detect_order_blocks",
    "detect_structure",
    "ema_bias",
    "find_swings",
    "has_inducement",
    "htf_aligned",
    "prepare",
    "price_position",
    "price_position_label",
    "recent_sweep",
    "rsi",
    "score_zone",
    "tag_premium_discount",
    "trading_session",
    "update_zone_lifecycle",
]
