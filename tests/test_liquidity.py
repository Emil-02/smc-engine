from smc_engine import (
    SwingPoint,
    build_liquidity_map,
    has_inducement,
    recent_sweep,
)
from smc_engine.liquidity import _find_equals

from .conftest import make_df


def test_equal_highs_cluster():
    swings = [SwingPoint(1, None, 100.0, True), SwingPoint(5, None, 100.03, True),
              SwingPoint(9, None, 103.0, True)]
    pools = _find_equals(swings, tol=0.04, is_high=True)
    assert len(pools) == 1
    p = pools[0]
    assert (p.label, p.price, p.touches, p.index) == ("EQH", 100.03, 2, 5)


def _sweep_df():
    rows = [(99, 99.5, 98.5, 99)] * 10
    rows[2] = (99, 100, 98.8, 99.5)       # swing high @100
    rows[5] = (99.4, 100.5, 99.2, 99.5)   # wick above, close back below -> sweep
    rows[7] = (99.5, 101, 99.4, 100.8)    # closes above -> break, not a sweep
    return make_df(rows)


def test_sweep_marking():
    df = _sweep_df()
    swing = SwingPoint(2, df["time"][2], 100.0, True)
    pools = build_liquidity_map(df, [swing])
    bsl = [p for p in pools if p.label == "BSL"]
    assert len(bsl) == 1
    assert bsl[0].sweep_indices == (5,)
    assert bsl[0].swept and bsl[0].swept_time == df["time"][5]


def test_old_sweep_is_not_recent():
    df = _sweep_df()
    swing = SwingPoint(2, df["time"][2], 100.0, True)
    pool = build_liquidity_map(df, [swing], recent_sweep_bars=4)[0]
    assert pool.sweep_indices == (5,) and not pool.swept


def test_recent_sweep_window():
    df = _sweep_df()
    swing = SwingPoint(2, df["time"][2], 100.0, True)
    pools = build_liquidity_map(df, [swing])
    # a BSL sweep supports bearish zones only
    assert recent_sweep(pools, zone_index=6, lookback_bars=3, direction_bullish=False)
    assert not recent_sweep(pools, zone_index=6, lookback_bars=3, direction_bullish=True)
    assert not recent_sweep(pools, zone_index=4, lookback_bars=3, direction_bullish=False)
    assert not recent_sweep(pools, zone_index=6, lookback_bars=1, direction_bullish=False)


def test_inducement():
    minor = [SwingPoint(4, None, 106, False), SwingPoint(8, None, 105, False),
             SwingPoint(9, None, 95, True)]
    assert has_inducement(minor, zone_top=104, zone_bottom=100, zone_index=5,
                          direction_bullish=True)
    assert not has_inducement(minor[:1], 104, 100, 5, True)
    assert has_inducement(minor, zone_top=110, zone_bottom=96, zone_index=5,
                          direction_bullish=False)


def test_empty_frame():
    assert build_liquidity_map(make_df([(1, 1, 1, 1)]).iloc[:0], []) == []
