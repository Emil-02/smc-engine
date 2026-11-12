"""Liquidity: buy/sell-side pools, equal highs/lows, sweeps and inducement.

- BSL (buy-side liquidity): resting buy stops ABOVE swing highs / equal highs.
- SSL (sell-side liquidity): resting sell stops BELOW swing lows / equal lows.
- Sweep: a wick trades through the level but the candle closes back on the original side.
- Inducement (IDM): a minor swing in front of a zone that lures early entries.
"""

from __future__ import annotations

from bisect import bisect_left

import numpy as np
import pandas as pd

from .models import LiquidityPool, SwingPoint


def build_liquidity_map(
    df: pd.DataFrame,
    swings: list[SwingPoint],
    eq_tolerance_pct: float = 0.04,
    recent_swings: int = 5,
    recent_sweep_bars: int = 200,
) -> list[LiquidityPool]:
    """Equal highs/lows (swings within ``eq_tolerance_pct`` % of the last close) plus the
    last ``recent_swings`` swing highs and lows, each annotated with its sweeps."""
    pools: list[LiquidityPool] = []
    if df.empty:
        return pools
    highs = [s for s in swings if s.is_high]
    lows = [s for s in swings if not s.is_high]
    tol = float(df["close"].iloc[-1]) * eq_tolerance_pct / 100.0

    pools += _find_equals(highs, tol, is_high=True)
    pools += _find_equals(lows, tol, is_high=False)
    for s in highs[-recent_swings:]:
        pools.append(LiquidityPool(price=s.price, is_buy_side=True, time=s.time, index=s.index))
    for s in lows[-recent_swings:]:
        pools.append(LiquidityPool(price=s.price, is_buy_side=False, time=s.time, index=s.index))

    _mark_sweeps(df, pools, recent_sweep_bars)
    return pools


def _find_equals(swings: list[SwingPoint], tol: float, is_high: bool) -> list[LiquidityPool]:
    pools: list[LiquidityPool] = []
    used: set[int] = set()
    for i in range(len(swings)):
        if i in used:
            continue
        cluster = [swings[i]]
        for j in range(i + 1, len(swings)):
            if abs(swings[j].price - swings[i].price) <= tol:
                cluster.append(swings[j])
                used.add(j)
        if len(cluster) >= 2:
            level = max(s.price for s in cluster) if is_high else min(s.price for s in cluster)
            pools.append(LiquidityPool(
                price=level, is_buy_side=is_high, kind="EQH" if is_high else "EQL",
                touches=len(cluster), time=cluster[-1].time, index=cluster[-1].index,
            ))
    return pools


def _mark_sweeps(df: pd.DataFrame, pools: list[LiquidityPool], recent_sweep_bars: int) -> None:
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    c = df["close"].to_numpy()
    t = df["time"].to_numpy()
    n = len(df)
    for p in pools:
        start = p.index + 1 if p.index >= 0 else 0
        if p.is_buy_side:
            mask = (h[start:] > p.price) & (c[start:] < p.price)
        else:
            mask = (l[start:] < p.price) & (c[start:] > p.price)
        idx = np.nonzero(mask)[0] + start
        p.sweep_indices = tuple(int(k) for k in idx)
        if len(idx) and idx[-1] > max(0, n - recent_sweep_bars):
            p.swept = True
            p.swept_time = pd.Timestamp(t[idx[-1]]).to_pydatetime()


def recent_sweep(
    pools: list[LiquidityPool], zone_index: int, lookback_bars: int, direction_bullish: bool
) -> bool:
    """Was opposite-side liquidity swept within ``lookback_bars`` bars up to and including
    ``zone_index``? Bullish zones look for SSL sweeps, bearish zones for BSL sweeps.
    Sweeps after the zone formed are ignored."""
    lo = max(0, zone_index + 1 - lookback_bars)
    for p in pools:
        if p.is_buy_side == direction_bullish or not p.sweep_indices:
            continue
        k = bisect_left(p.sweep_indices, lo)
        if k < len(p.sweep_indices) and p.sweep_indices[k] <= zone_index:
            return True
    return False


def has_inducement(
    minor_swings: list[SwingPoint],
    zone_top: float,
    zone_bottom: float,
    zone_index: int,
    direction_bullish: bool,
) -> bool:
    """A minor swing formed after the zone and sitting in front of it: a minor swing LOW
    above a bullish zone, or a minor swing HIGH below a bearish zone."""
    for s in minor_swings:
        if s.index <= zone_index:
            continue
        if direction_bullish and not s.is_high and s.price > zone_top:
            return True
        if not direction_bullish and s.is_high and s.price < zone_bottom:
            return True
    return False
