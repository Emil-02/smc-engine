"""High-level pipeline and confluence scoring.

candles -> swings (major + minor) -> structure (BOS/CHoCH) -> liquidity (pools, sweeps)
-> zones (OB / FVG / breaker) -> lifecycle -> premium/discount + OTE -> per-zone context.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from . import indicators
from ._frame import prepare
from .liquidity import build_liquidity_map, has_inducement, recent_sweep
from .models import Direction, LiquidityPool, StructureBreak, SwingPoint, Zone, ZoneKind
from .structure import dealing_range, detect_structure
from .swings import find_swings
from .zones import (
    detect_breakers,
    detect_fvg,
    detect_order_blocks,
    tag_premium_discount,
    update_zone_lifecycle,
)


@dataclass
class SMCConfig:
    swing_lookback: int = 3
    """Fractal size for major swings (structure, liquidity, dealing range)."""
    minor_swing_lookback: int = 1
    """Fractal size for minor swings (inducement)."""
    eq_tolerance_pct: float = 0.04
    """Equal highs/lows tolerance, in percent of the last close."""
    displacement_atr_mult: float = 1.3
    """Minimum impulsive leg (in ATR) for an order block to count."""
    fvg_min_gap_atr: float = 0.15
    ote_min: float = 0.618
    ote_max: float = 0.79
    zone_max_age_bars: int = 250
    max_zones_per_kind: int = 25
    sweep_lookback_bars: int = 40
    """How far before a zone to look for a liquidity sweep."""
    recent_sweep_bars: int = 200
    """A pool counts as ``swept`` if its last sweep is within this many bars."""
    atr_period: int = 14
    rsi_period: int = 14
    min_bars: int = 50
    """Fewer bars than this returns an empty analysis."""


@dataclass
class Analysis:
    """Everything detected on one timeframe."""

    symbol: str = ""
    timeframe: str = ""
    df: pd.DataFrame | None = None
    swings: list[SwingPoint] = field(default_factory=list)
    minor_swings: list[SwingPoint] = field(default_factory=list)
    breaks: list[StructureBreak] = field(default_factory=list)
    trend: str = "NEUTRAL"
    liquidity: list[LiquidityPool] = field(default_factory=list)
    zones: list[Zone] = field(default_factory=list)
    dealing: tuple[float, float] | None = None
    atr: float = 0.0
    rsi: float = 50.0

    @property
    def active_zones(self) -> list[Zone]:
        return [z for z in self.zones if not z.invalidated]

    # ---- DataFrame views -------------------------------------------------
    def swings_frame(self) -> pd.DataFrame:
        rows = [{"index": s.index, "time": s.time, "price": s.price,
                 "type": "high" if s.is_high else "low", "kind": s.kind.value}
                for s in self.swings]
        return pd.DataFrame(rows, columns=["index", "time", "price", "type", "kind"])

    def breaks_frame(self) -> pd.DataFrame:
        rows = [{"index": b.break_index, "time": b.break_time, "event": b.event.value,
                 "direction": b.direction.value, "level": b.broken_level}
                for b in self.breaks]
        return pd.DataFrame(rows, columns=["index", "time", "event", "direction", "level"])

    def zones_frame(self) -> pd.DataFrame:
        cols = ["index", "time", "kind", "direction", "top", "bottom", "displacement",
                "swept_liquidity", "has_inducement", "in_ote", "in_discount",
                "mitigated", "invalidated", "touches"]
        rows = []
        for z in self.zones:
            d = asdict(z)
            d["kind"], d["direction"] = z.kind.value, z.direction.value
            rows.append({c: d[c] for c in cols})
        return pd.DataFrame(rows, columns=cols)

    def liquidity_frame(self) -> pd.DataFrame:
        rows = [{"index": p.index, "time": p.time, "price": p.price, "label": p.label,
                 "touches": p.touches, "swept": p.swept, "swept_time": p.swept_time,
                 "sweeps": len(p.sweep_indices)}
                for p in self.liquidity]
        return pd.DataFrame(rows, columns=["index", "time", "price", "label", "touches",
                                           "swept", "swept_time", "sweeps"])


def analyze(
    df: pd.DataFrame,
    config: SMCConfig | None = None,
    *,
    symbol: str = "",
    timeframe: str = "",
) -> Analysis:
    """Run the full Smart Money Concepts pipeline on OHLC data.

    ``df`` needs ``open``/``high``/``low``/``close`` columns (any capitalisation) and
    either a ``time`` column or a ``DatetimeIndex``, sorted ascending. Timezone-aware
    times are converted to naive UTC. Bar indices in the result refer to row positions.
    """
    cfg = config or SMCConfig()
    data = prepare(df)
    a = Analysis(symbol=symbol, timeframe=timeframe, df=data)
    if len(data) < cfg.min_bars:
        return a

    a.atr = indicators.atr(data, cfg.atr_period)
    a.rsi = indicators.rsi(data, cfg.rsi_period)
    a.swings = find_swings(data, cfg.swing_lookback)
    a.minor_swings = find_swings(data, cfg.minor_swing_lookback)
    a.breaks, a.trend = detect_structure(data, a.swings)
    a.liquidity = build_liquidity_map(
        data, a.swings, cfg.eq_tolerance_pct, recent_sweep_bars=cfg.recent_sweep_bars
    )
    a.dealing = dealing_range(a.swings)

    tags = {"timeframe": timeframe, "symbol": symbol}
    obs = detect_order_blocks(data, a.breaks, a.atr, cfg.displacement_atr_mult, **tags)
    fvgs = detect_fvg(data, a.atr, cfg.fvg_min_gap_atr, **tags)
    breakers = detect_breakers(data, obs)
    zones = obs + fvgs + breakers

    update_zone_lifecycle(data, zones)
    tag_premium_discount(zones, a.dealing, cfg.ote_min, cfg.ote_max)
    for z in zones:
        bullish = z.direction == Direction.BULLISH
        z.swept_liquidity = recent_sweep(a.liquidity, z.index, cfg.sweep_lookback_bars, bullish)
        z.has_inducement = has_inducement(a.minor_swings, z.top, z.bottom, z.index, bullish)

    a.zones = _prune(zones, len(data), cfg)
    return a


def _prune(zones: list[Zone], n_bars: int, cfg: SMCConfig) -> list[Zone]:
    """Drop invalidated and stale zones, keep the newest ``max_zones_per_kind`` per kind."""
    fresh = [z for z in zones
             if not z.invalidated and (n_bars - z.index) <= cfg.zone_max_age_bars]
    out: list[Zone] = []
    for kind in ZoneKind:
        of_kind = sorted((z for z in fresh if z.kind == kind), key=lambda z: z.index)
        out.extend(of_kind[-cfg.max_zones_per_kind:])
    return sorted(out, key=lambda z: z.index)


def score_zone(
    zone: Zone, analysis: Analysis, htf_bias: dict[str, str] | None = None
) -> tuple[int, list[str]]:
    """Confluence score 0-100 for a zone, with human-readable reasons.

    ``htf_bias`` maps higher timeframes to ``"BULLISH"``/``"BEARISH"``/``"NEUTRAL"``,
    e.g. ``{"H1": "BULLISH", "H4": "NEUTRAL"}`` (see :func:`indicators.ema_bias` or the
    ``trend`` of a higher-timeframe :class:`Analysis`).
    """
    htf_bias = htf_bias or {}
    score = 0
    notes: list[str] = []
    bullish = zone.direction == Direction.BULLISH
    want = "BULLISH" if bullish else "BEARISH"

    agree = sum(1 for b in htf_bias.values() if b == want)
    disagree = sum(1 for b in htf_bias.values() if b not in (want, "NEUTRAL"))
    if agree == len(htf_bias) and agree > 0:
        score += 25
        notes.append(f"Full HTF {want} bias ({'/'.join(htf_bias)})")
    elif agree > disagree:
        score += 15
        notes.append(f"Majority HTF {want} bias")
    elif disagree > agree:
        score -= 15
        notes.append(f"Against HTF bias ({disagree} timeframe(s) opposite)")

    if analysis.trend == want:
        score += 15
        notes.append(f"{analysis.timeframe or 'Entry'} structure {analysis.trend} (aligned)")
    elif analysis.trend not in (want, "NEUTRAL"):
        score -= 10
        notes.append(f"{analysis.timeframe or 'Entry'} structure {analysis.trend} (opposite)")

    if zone.displacement >= 2.0:
        score += 15
        notes.append(f"Strong displacement ({zone.displacement:.1f}x ATR)")
    elif zone.displacement >= 1.3:
        score += 10
        notes.append(f"Decent displacement ({zone.displacement:.1f}x ATR)")

    if zone.swept_liquidity:
        score += 15
        notes.append(f"{'SSL' if bullish else 'BSL'} liquidity swept before the zone")

    if zone.has_inducement:
        score += 8
        notes.append("Inducement (IDM) in front of the zone")

    if zone.in_discount is True and bullish:
        score += 10
        notes.append("Demand zone in DISCOUNT")
    elif zone.in_discount is False and not bullish:
        score += 10
        notes.append("Supply zone in PREMIUM")
    elif zone.in_discount is not None:
        score -= 8
        notes.append("Zone on the wrong side of equilibrium")

    if zone.in_ote:
        score += 8
        notes.append("Zone inside OTE (61.8-79%)")

    if zone.touches <= 1:
        score += 7
        notes.append("Fresh zone (first tap)")
    elif zone.touches >= 3:
        score -= 5
        notes.append(f"Zone tested {zone.touches}x (weakened)")

    if zone.kind == ZoneKind.ORDER_BLOCK and zone.linked_bos is not None:
        score += 7
        notes.append(
            f"Order block from {zone.linked_bos.event.value} {zone.linked_bos.direction.value}"
        )
    elif zone.kind == ZoneKind.BREAKER:
        score += 5
        notes.append("Breaker block (polarity flip)")
    elif zone.kind == ZoneKind.FVG and not zone.swept_liquidity:
        score -= 8
        notes.append("Plain FVG without a sweep (historically weak)")

    if bullish and analysis.rsi <= 35:
        score += 5
        notes.append(f"RSI oversold ({analysis.rsi:.0f})")
    elif not bullish and analysis.rsi >= 65:
        score += 5
        notes.append(f"RSI overbought ({analysis.rsi:.0f})")

    return max(0, min(100, score)), notes


def htf_aligned(direction: Direction, htf_bias: dict[str, str], mode: str = "strict") -> bool:
    """``strict``: no higher timeframe disagrees and at least one agrees.
    ``first``: only the first (closest) higher timeframe in ``htf_bias`` must agree."""
    want = "BULLISH" if direction == Direction.BULLISH else "BEARISH"
    if mode == "first":
        return bool(htf_bias) and htf_bias[next(iter(htf_bias))] == want
    if mode != "strict":
        raise ValueError("mode must be 'strict' or 'first'")
    against = "BEARISH" if want == "BULLISH" else "BULLISH"
    agree = sum(1 for b in htf_bias.values() if b == want)
    disagree = sum(1 for b in htf_bias.values() if b == against)
    return agree > 0 and disagree == 0


def detect_ltf_choch(analysis: Analysis, direction: Direction, within_bars: int = 12) -> bool:
    """Entry confirmation: a lower-timeframe CHoCH in ``direction`` within the last
    ``within_bars`` bars of ``analysis``."""
    if not analysis.breaks or analysis.df is None:
        return False
    n = len(analysis.df)
    for br in reversed(analysis.breaks):
        if n - br.break_index > within_bars:
            break
        if br.event.value == "CHoCH" and br.direction == direction:
            return True
    return False
