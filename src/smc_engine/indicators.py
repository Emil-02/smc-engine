"""Classic indicators used as confluence: ATR, RSI, EMA bias and trading session."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

_LONDON = ZoneInfo("Europe/London")
_NEW_YORK = ZoneInfo("America/New_York")
_UTC = ZoneInfo("UTC")


def atr(df: pd.DataFrame, period: int = 14) -> float:
    """Wilder's Average True Range of the last bar (simple mean range on short data)."""
    if len(df) < period + 1:
        return float((df["high"] - df["low"]).mean() or 0.0)
    h, l, c = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    prev_c = np.roll(c, 1)
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))[1:]
    return float(pd.Series(tr).ewm(alpha=1 / period, adjust=False).mean().iloc[-1])


def rsi(df: pd.DataFrame, period: int = 14) -> float:
    """Wilder's RSI of the last bar; 50 when there is not enough data."""
    if len(df) < period + 1:
        return 50.0
    delta = df["close"].diff().dropna()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    g, lo = float(gain.iloc[-1]), float(loss.iloc[-1])
    if lo == 0:
        return 100.0 if g > 0 else 50.0
    return float(100 - 100 / (1 + g / lo))


def ema_bias(df: pd.DataFrame, fast: int = 21, slow: int = 50) -> str:
    """``"BULLISH"`` when EMA(fast) > EMA(slow) and price > EMA(fast), ``"BEARISH"`` for
    the mirror case, otherwise ``"NEUTRAL"``."""
    if len(df) < slow + 5:
        return "NEUTRAL"
    e_fast = df["close"].ewm(span=fast, adjust=False).mean().iloc[-1]
    e_slow = df["close"].ewm(span=slow, adjust=False).mean().iloc[-1]
    price = df["close"].iloc[-1]
    if e_fast > e_slow and price > e_fast:
        return "BULLISH"
    if e_fast < e_slow and price < e_fast:
        return "BEARISH"
    return "NEUTRAL"


def trading_session(t: datetime) -> str:
    """Forex session for a UTC timestamp (naive values are treated as UTC), using local
    exchange hours so daylight saving time is handled automatically:
    London 08-13 London time, overlap 13 London to 12 New York, New York 12-17 NY time."""
    ts = pd.Timestamp(t)
    utc = ts.tz_localize(_UTC) if ts.tzinfo is None else ts.tz_convert(_UTC)
    ldn = utc.tz_convert(_LONDON).hour
    ny = utc.tz_convert(_NEW_YORK).hour
    if 8 <= ldn < 13:
        return "London"
    if ldn >= 13 and ny < 12:
        return "London-NY Overlap"
    if 12 <= ny < 17:
        return "New York"
    # Remaining hours are either before the London open or after the New York close.
    if ldn < 8:
        return "Asia"
    return "Sydney/Late NY"
