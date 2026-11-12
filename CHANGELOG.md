# Changelog

## 0.1.0

First release, extracted from a private XAU/USD signal system. Detection output is
identical to the original engine. A parity check over 30 random datasets matched every
zone, break, liquidity pool and score.

- `analyze()` pipeline with `SMCConfig`, `Analysis` and DataFrame views
  (`zones_frame`, `breaks_frame`, `swings_frame`, `liquidity_frame`).
- Swings, BOS/CHoCH (with `confirm_lag` for point-in-time use), order blocks, FVG,
  breaker blocks, liquidity pools, sweeps, inducement, premium/discount, OTE and lifecycle.
- `score_zone()` confluence score with reasons, `htf_aligned()`, `detect_ltf_choch()`.
- ATR, RSI, EMA bias and a DST-aware `trading_session()`.
- Optional matplotlib `plot()`.
- Accepts any column capitalisation, a `DatetimeIndex`, and timezone-aware times.

Differences from the original code:

- `trading_session()` now labels the hour before the London open as "Asia" in winter too.
  The original used a fixed 07:00 UTC cut-off that only fit summer time.
