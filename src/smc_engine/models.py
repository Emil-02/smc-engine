"""Core data structures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Direction(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class ZoneKind(str, Enum):
    ORDER_BLOCK = "OB"
    FVG = "FVG"
    BREAKER = "BB"


class StructureEvent(str, Enum):
    BOS = "BOS"
    """Break of Structure: trend continuation."""
    CHOCH = "CHoCH"
    """Change of Character: potential reversal."""


class SwingKind(str, Enum):
    HH = "HH"
    HL = "HL"
    LH = "LH"
    LL = "LL"
    H = "H"
    """First swing high (nothing to compare against yet)."""
    L = "L"
    """First swing low."""


@dataclass
class SwingPoint:
    index: int
    """Row position in the analysed DataFrame."""
    time: datetime
    price: float
    is_high: bool
    kind: SwingKind = SwingKind.H


@dataclass
class StructureBreak:
    event: StructureEvent
    direction: Direction
    broken_level: float
    break_time: datetime
    break_index: int
    swing_ref: SwingPoint | None = None


@dataclass
class LiquidityPool:
    """Resting liquidity above swing highs (buy side) or below swing lows (sell side)."""

    price: float
    is_buy_side: bool
    kind: str = "SWING"
    """``SWING``, ``EQH`` (equal highs) or ``EQL`` (equal lows)."""
    touches: int = 1
    time: datetime | None = None
    index: int = -1
    """Row of the (last) swing that formed the pool; sweeps are searched after it."""
    swept: bool = False
    """Swept within the last ``recent_sweep_bars`` bars."""
    swept_time: datetime | None = None
    sweep_indices: tuple[int, ...] = ()
    """Every bar that swept the level (wick through, close back), ascending."""

    @property
    def label(self) -> str:
        if self.kind in ("EQH", "EQL"):
            return self.kind
        return "BSL" if self.is_buy_side else "SSL"


@dataclass
class Zone:
    """Point of interest: order block, fair value gap or breaker block."""

    kind: ZoneKind
    direction: Direction
    """BULLISH = demand (look for buys), BEARISH = supply (look for sells)."""
    top: float
    bottom: float
    time: datetime
    index: int
    timeframe: str = ""
    symbol: str = ""
    displacement: float = 0.0
    """Strength of the move away from the zone, in ATR multiples."""
    linked_bos: StructureBreak | None = None
    swept_liquidity: bool = False
    """Opposite-side liquidity was swept shortly before the zone formed."""
    has_inducement: bool = False
    """A minor swing (inducement) sits between price and the zone."""
    in_ote: bool = False
    """Zone midpoint lies in the Optimal Trade Entry retracement band."""
    in_discount: bool | None = None
    """True = below equilibrium of the dealing range, False = premium, None = unknown."""
    mitigated: bool = False
    mitigated_time: datetime | None = None
    invalidated: bool = False
    touches: int = 0

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2.0

    @property
    def height(self) -> float:
        return self.top - self.bottom

    def contains(self, price: float) -> bool:
        return self.bottom <= price <= self.top

    @property
    def id(self) -> str:
        return (
            f"{self.symbol}|{self.timeframe}|{self.kind.value}|"
            f"{self.direction.value}|{self.time:%Y%m%d%H%M}"
        )

    @property
    def label(self) -> str:
        sign = "+" if self.direction == Direction.BULLISH else "-"
        return f"{self.kind.value}{sign} {self.timeframe}".strip()
