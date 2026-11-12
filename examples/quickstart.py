"""Run: uv run --extra plot python examples/quickstart.py [your.csv]

The CSV needs time, open, high, low, close columns. Without a file a random walk is used.
"""

import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import smc_engine as smc
from smc_engine.plot import plot


def sample_data(n: int = 500, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 2350 + np.cumsum(rng.normal(0, 2.5, n))
    open_ = np.r_[close[0], close[:-1]]
    spread = np.abs(rng.normal(0, 1.5, n))
    return pd.DataFrame({
        "time": pd.date_range("2026-03-02", periods=n, freq="15min"),
        "open": open_,
        "high": np.maximum(open_, close) + spread,
        "low": np.minimum(open_, close) - spread,
        "close": close,
    })


df = pd.read_csv(sys.argv[1], parse_dates=["time"]) if len(sys.argv) > 1 else sample_data()
result = smc.analyze(df, symbol="DEMO", timeframe="M15")

print(f"Trend: {result.trend}   ATR: {result.atr:.2f}   RSI: {result.rsi:.0f}")
print(f"Price is in {smc.price_position_label(df['close'].iloc[-1], result.dealing)}\n")
print(result.breaks_frame().tail(5).to_string(index=False), "\n")

htf = {"H1": "BULLISH", "H4": "NEUTRAL"}
for zone in result.active_zones[-5:]:
    score, notes = smc.score_zone(zone, result, htf)
    span = f"{zone.bottom:9.2f}-{zone.top:9.2f}"
    print(f"{zone.label:8} {span}  score {score:3d}  | {'; '.join(notes)}")

plot(result, last=160)
plt.tight_layout()
plt.savefig("smc-example.png", dpi=130)
print("\nChart saved to smc-example.png")
