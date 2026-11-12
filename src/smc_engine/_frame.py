"""Input validation and normalisation."""

from __future__ import annotations

import pandas as pd

REQUIRED = ("open", "high", "low", "close")


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with lowercase OHLC columns, a ``time`` column and a 0..n-1 index.

    Accepts either a ``time`` column (any capitalisation) or a ``DatetimeIndex``.
    Rows must already be sorted by time.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("expected a pandas DataFrame")
    out = df.rename(columns={c: c.lower() for c in df.columns if isinstance(c, str)})
    missing = [c for c in REQUIRED if c not in out.columns]
    if missing:
        raise ValueError(f"missing OHLC column(s): {', '.join(missing)}")
    if "time" not in out.columns:
        if isinstance(out.index, pd.DatetimeIndex):
            out = out.rename_axis("time").reset_index()
        else:
            raise ValueError("need a 'time' column or a DatetimeIndex")
    out = out.reset_index(drop=True)
    out["time"] = pd.to_datetime(out["time"])
    if out["time"].dt.tz is not None:
        out["time"] = out["time"].dt.tz_convert("UTC").dt.tz_localize(None)
    if not out["time"].is_monotonic_increasing:
        raise ValueError("rows must be sorted by time (ascending)")
    for c in REQUIRED:
        out[c] = out[c].astype(float)
    return out
