from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def make_df(candles: list[tuple[float, float, float, float]], freq: str = "15min") -> pd.DataFrame:
    """Build an OHLC frame from (open, high, low, close) tuples."""
    o, h, l, c = zip(*candles, strict=True)
    return pd.DataFrame({
        "time": pd.date_range("2026-01-05 00:00", periods=len(candles), freq=freq),
        "open": o, "high": h, "low": l, "close": c,
    })


def from_closes(closes: list[float], wick: float = 0.2) -> pd.DataFrame:
    """Candles whose open is the previous close, with a fixed wick on both sides."""
    rows = []
    prev = closes[0]
    for c in closes:
        o = prev
        rows.append((o, max(o, c) + wick, min(o, c) - wick, c))
        prev = c
    return make_df(rows)


@pytest.fixture
def random_walk() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    n = 600
    close = 2000 + np.cumsum(rng.normal(0, 2.0, n))
    open_ = np.r_[close[0], close[:-1]]
    spread = np.abs(rng.normal(0, 1.2, n))
    return pd.DataFrame({
        "time": pd.date_range("2026-01-05", periods=n, freq="15min"),
        "open": open_,
        "high": np.maximum(open_, close) + spread,
        "low": np.minimum(open_, close) - spread,
        "close": close,
    })
