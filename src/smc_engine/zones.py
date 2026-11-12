"""Points of interest: order blocks, fair value gaps, breaker blocks, their lifecycle
(mitigation / invalidation) and premium/discount + OTE context."""

from __future__ import annotations

import pandas as pd

from .models import Direction, StructureBreak, Zone, ZoneKind


def detect_fvg(
    df: pd.DataFrame,
    atr_val: float,
    min_gap_atr: float = 0.15,
    *,
    timeframe: str = "",
    symbol: str = "",
) -> list[Zone]:
    """Three-candle fair value gaps larger than ``atr_val * min_gap_atr``.

    Bullish: ``high[c1] < low[c3]``. Bearish: ``low[c1] > high[c3]``.
    The zone is stamped on the middle candle.
    """
    zones: list[Zone] = []
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    t = df["time"].to_numpy()
    min_gap = atr_val * min_gap_atr

    for i in range(2, len(df)):
        gap_up = l[i] - h[i - 2]
        if gap_up > min_gap:
            zones.append(Zone(
                kind=ZoneKind.FVG, direction=Direction.BULLISH,
                top=float(l[i]), bottom=float(h[i - 2]),
                time=pd.Timestamp(t[i - 1]).to_pydatetime(), index=i - 1,
                timeframe=timeframe, symbol=symbol,
                displacement=gap_up / atr_val if atr_val else 0.0,
            ))
        gap_dn = l[i - 2] - h[i]
        if gap_dn > min_gap:
            zones.append(Zone(
                kind=ZoneKind.FVG, direction=Direction.BEARISH,
                top=float(l[i - 2]), bottom=float(h[i]),
                time=pd.Timestamp(t[i - 1]).to_pydatetime(), index=i - 1,
                timeframe=timeframe, symbol=symbol,
                displacement=gap_dn / atr_val if atr_val else 0.0,
            ))
    return zones


def detect_order_blocks(
    df: pd.DataFrame,
    breaks: list[StructureBreak],
    atr_val: float,
    displacement_atr_mult: float = 1.3,
    max_lookback: int = 15,
    *,
    timeframe: str = "",
    symbol: str = "",
) -> list[Zone]:
    """For every BOS/CHoCH, walk back (at most ``max_lookback`` bars) to the last
    opposite-colour candle before the impulsive leg. The leg from that candle to the
    breaking close must be at least ``atr_val * displacement_atr_mult``. When several
    breaks point at the same candle, the strongest displacement wins."""
    best: dict[int, Zone] = {}
    o = df["open"].to_numpy()
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    c = df["close"].to_numpy()
    t = df["time"].to_numpy()

    for br in breaks:
        bi = br.break_index
        bullish = br.direction == Direction.BULLISH
        ob_idx = None
        for k in range(bi, max(-1, bi - max_lookback), -1):
            candle_bear = c[k] < o[k]
            if bullish == candle_bear:
                ob_idx = k
                break
        if ob_idx is None:
            continue

        leg = float(c[bi] - l[ob_idx]) if bullish else float(h[ob_idx] - c[bi])
        disp = leg / atr_val if atr_val else 0.0
        if disp < displacement_atr_mult:
            continue

        prev = best.get(ob_idx)
        if prev is not None and prev.displacement >= disp:
            continue
        best[ob_idx] = Zone(
            kind=ZoneKind.ORDER_BLOCK,
            direction=Direction.BULLISH if bullish else Direction.BEARISH,
            top=float(h[ob_idx]), bottom=float(l[ob_idx]),
            time=pd.Timestamp(t[ob_idx]).to_pydatetime(), index=ob_idx,
            timeframe=timeframe, symbol=symbol,
            displacement=disp, linked_bos=br,
        )
    return sorted(best.values(), key=lambda z: z.index)


def detect_breakers(df: pd.DataFrame, order_blocks: list[Zone]) -> list[Zone]:
    """An order block closed through on its far side flips polarity into a breaker.
    The original order block is marked ``invalidated``."""
    zones: list[Zone] = []
    c = df["close"].to_numpy()
    t = df["time"].to_numpy()
    for ob in order_blocks:
        for i in range(ob.index + 1, len(df)):
            failed_demand = ob.direction == Direction.BULLISH and c[i] < ob.bottom
            failed_supply = ob.direction == Direction.BEARISH and c[i] > ob.top
            if failed_demand or failed_supply:
                zones.append(Zone(
                    kind=ZoneKind.BREAKER,
                    direction=Direction.BEARISH if failed_demand else Direction.BULLISH,
                    top=ob.top, bottom=ob.bottom,
                    time=pd.Timestamp(t[i]).to_pydatetime(), index=i,
                    timeframe=ob.timeframe, symbol=ob.symbol,
                    displacement=ob.displacement,
                ))
                ob.invalidated = True
                break
    return zones


def update_zone_lifecycle(df: pd.DataFrame, zones: list[Zone]) -> None:
    """Mark zones ``mitigated`` (first touch, counting ``touches``) or ``invalidated``
    (a close beyond the far side), starting two bars after the zone formed."""
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    c = df["close"].to_numpy()
    t = df["time"].to_numpy()
    for z in zones:
        if z.invalidated:
            continue
        bullish = z.direction == Direction.BULLISH
        for i in range(z.index + 2, len(df)):
            if (bullish and c[i] < z.bottom) or (not bullish and c[i] > z.top):
                z.invalidated = True
                break
            if (bullish and l[i] <= z.top) or (not bullish and h[i] >= z.bottom):
                z.touches += 1
                if not z.mitigated:
                    z.mitigated = True
                    z.mitigated_time = pd.Timestamp(t[i]).to_pydatetime()


def tag_premium_discount(
    zones: list[Zone],
    dealing: tuple[float, float] | None,
    ote_min: float = 0.618,
    ote_max: float = 0.79,
) -> None:
    """Set ``in_discount`` (midpoint below 50% of the dealing range) and ``in_ote``
    (midpoint inside the ``ote_min``..``ote_max`` retracement band) on every zone."""
    if dealing is None:
        return
    lo, hi = dealing
    rng = hi - lo
    if rng <= 0:
        return
    eq = lo + rng * 0.5
    for z in zones:
        z.in_discount = z.mid < eq
        if z.direction == Direction.BULLISH:
            ote_hi = hi - rng * ote_min
            ote_lo = hi - rng * ote_max
        else:
            ote_lo = lo + rng * ote_min
            ote_hi = lo + rng * ote_max
        z.in_ote = min(ote_lo, ote_hi) <= z.mid <= max(ote_lo, ote_hi)


def price_position(price: float, dealing: tuple[float, float] | None) -> float | None:
    """Where ``price`` sits in the dealing range: 0 = range low, 1 = range high."""
    if dealing is None:
        return None
    lo, hi = dealing
    if hi <= lo:
        return None
    return (price - lo) / (hi - lo)


def price_position_label(price: float, dealing: tuple[float, float] | None) -> str:
    """``"PREMIUM (72%)"``, ``"DISCOUNT (31%)"`` or ``"UNKNOWN"``."""
    ratio = price_position(price, dealing)
    if ratio is None:
        return "UNKNOWN"
    side = "PREMIUM" if ratio >= 0.5 else "DISCOUNT"
    return f"{side} ({ratio * 100:.0f}%)"
