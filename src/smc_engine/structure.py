"""Market structure: Break of Structure (BOS) and Change of Character (CHoCH).

- Bullish trend: a close above the last swing high is a bullish BOS (continuation);
  a close below the protective swing low is a bearish CHoCH (reversal).
- Bearish trend: the mirror image.
- Breaks are measured on the CLOSE, not the wick, so liquidity sweeps are not counted.
"""

from __future__ import annotations

import pandas as pd

from .models import Direction, StructureBreak, StructureEvent, SwingPoint


def detect_structure(
    df: pd.DataFrame, swings: list[SwingPoint], confirm_lag: int = 0
) -> tuple[list[StructureBreak], str]:
    """Return ``(breaks in chronological order, final trend)``.

    The trend is ``"BULLISH"``, ``"BEARISH"`` or ``"NEUTRAL"``.

    ``confirm_lag``: a swing only becomes usable once ``swing.index + confirm_lag < bar``.
    Set it to the swing lookback when you need point-in-time results (e.g. a per-bar
    higher-timeframe bias in a backtest) so that no future bars leak in.
    """
    breaks: list[StructureBreak] = []
    trend = "NEUTRAL"

    highs = [s for s in swings if s.is_high]
    lows = [s for s in swings if not s.is_high]
    if not highs or not lows:
        return breaks, trend

    c = df["close"].to_numpy()
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    t = df["time"].to_numpy()

    hi_idx = 0
    lo_idx = 0
    cur_high: SwingPoint | None = None
    cur_low: SwingPoint | None = None

    for i in range(len(df)):
        while hi_idx < len(highs) and highs[hi_idx].index + confirm_lag < i:
            cur_high = highs[hi_idx]
            hi_idx += 1
        while lo_idx < len(lows) and lows[lo_idx].index + confirm_lag < i:
            cur_low = lows[lo_idx]
            lo_idx += 1
        if cur_high is None or cur_low is None:
            continue

        close_i = float(c[i])
        time_i = pd.Timestamp(t[i]).to_pydatetime()

        if close_i > cur_high.price:
            event = StructureEvent.BOS if trend in ("BULLISH", "NEUTRAL") else StructureEvent.CHOCH
            breaks.append(StructureBreak(
                event=event, direction=Direction.BULLISH, broken_level=cur_high.price,
                break_time=time_i, break_index=i, swing_ref=cur_high,
            ))
            trend = "BULLISH"
            # Until a newer swing high confirms, the breakout bar's high is the new level.
            cur_high = _next_active(highs, hi_idx, i, confirm_lag) or SwingPoint(
                index=i, time=time_i, price=float(h[i]), is_high=True
            )
        elif close_i < cur_low.price:
            event = StructureEvent.BOS if trend in ("BEARISH", "NEUTRAL") else StructureEvent.CHOCH
            breaks.append(StructureBreak(
                event=event, direction=Direction.BEARISH, broken_level=cur_low.price,
                break_time=time_i, break_index=i, swing_ref=cur_low,
            ))
            trend = "BEARISH"
            cur_low = _next_active(lows, lo_idx, i, confirm_lag) or SwingPoint(
                index=i, time=time_i, price=float(l[i]), is_high=False
            )

    return breaks, trend


def _next_active(
    swings: list[SwingPoint], start: int, bar_i: int, confirm_lag: int = 0
) -> SwingPoint | None:
    cand = None
    for k in range(start, len(swings)):
        if swings[k].index + confirm_lag <= bar_i:
            cand = swings[k]
        else:
            break
    return cand


def dealing_range(swings: list[SwingPoint]) -> tuple[float, float] | None:
    """``(low, high)`` of the latest major swing low and swing high, used for
    premium/discount and OTE. Returns ``None`` when no valid range exists."""
    highs = [s for s in swings if s.is_high]
    lows = [s for s in swings if not s.is_high]
    if not highs or not lows:
        return None
    hi = highs[-1].price
    lo = lows[-1].price
    if hi <= lo:
        recent = swings[-6:]
        recent_highs = [s.price for s in recent if s.is_high]
        recent_lows = [s.price for s in recent if not s.is_high]
        if recent_highs:
            hi = max(recent_highs)
        if recent_lows:
            lo = min(recent_lows)
    if hi <= lo:
        return None
    return lo, hi
