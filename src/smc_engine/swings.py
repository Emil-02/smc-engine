"""Fractal swing detection with HH / HL / LH / LL labelling."""

from __future__ import annotations

import pandas as pd

from .models import SwingKind, SwingPoint


def find_swings(df: pd.DataFrame, lookback: int = 3) -> list[SwingPoint]:
    """Bar ``i`` is a swing high when its high is the strict first maximum of the window
    ``[i - lookback, i + lookback]`` (likewise for lows). A bar is never both.

    Use a large ``lookback`` for major structure and ``1`` for minor swings (inducement).
    The last ``lookback`` bars can never be swings because they are not confirmed yet.
    """
    if lookback < 1:
        raise ValueError("lookback must be >= 1")
    swings: list[SwingPoint] = []
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    t = df["time"].to_numpy()

    for i in range(lookback, len(df) - lookback):
        win_h = h[i - lookback : i + lookback + 1]
        win_l = l[i - lookback : i + lookback + 1]
        if h[i] == win_h.max() and win_h.argmax() == lookback:
            swings.append(
                SwingPoint(index=i, time=pd.Timestamp(t[i]).to_pydatetime(),
                           price=float(h[i]), is_high=True)
            )
        elif l[i] == win_l.min() and win_l.argmin() == lookback:
            swings.append(
                SwingPoint(index=i, time=pd.Timestamp(t[i]).to_pydatetime(),
                           price=float(l[i]), is_high=False)
            )

    _classify(swings)
    return swings


def _classify(swings: list[SwingPoint]) -> None:
    last_high: SwingPoint | None = None
    last_low: SwingPoint | None = None
    for s in swings:
        if s.is_high:
            if last_high is None:
                s.kind = SwingKind.H
            else:
                s.kind = SwingKind.HH if s.price > last_high.price else SwingKind.LH
            last_high = s
        else:
            if last_low is None:
                s.kind = SwingKind.L
            else:
                s.kind = SwingKind.HL if s.price > last_low.price else SwingKind.LL
            last_low = s
