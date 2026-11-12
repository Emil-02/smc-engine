from smc_engine import (
    Direction,
    StructureEvent,
    SwingPoint,
    dealing_range,
    detect_structure,
)

from .conftest import from_closes


def _setup():
    df = from_closes([10, 11, 10, 11, 12.5, 12, 8.5, 8.4])
    t = df["time"]
    swings = [
        SwingPoint(index=1, time=t[1], price=12, is_high=True),
        SwingPoint(index=2, time=t[2], price=9, is_high=False),
    ]
    return df, swings


def test_bos_then_choch():
    df, swings = _setup()
    breaks, trend = detect_structure(df, swings)
    assert [(b.event, b.direction, b.broken_level, b.break_index) for b in breaks] == [
        (StructureEvent.BOS, Direction.BULLISH, 12, 4),
        (StructureEvent.CHOCH, Direction.BEARISH, 9, 6),
    ]
    assert trend == "BEARISH"
    assert breaks[0].swing_ref is swings[0]


def test_confirm_lag_delays_swings():
    df, swings = _setup()
    breaks, trend = detect_structure(df, swings, confirm_lag=3)
    assert [(b.event, b.direction, b.break_index) for b in breaks] == [
        (StructureEvent.BOS, Direction.BEARISH, 6),
    ]
    assert trend == "BEARISH"


def test_needs_both_sides():
    df, swings = _setup()
    assert detect_structure(df, swings[:1]) == ([], "NEUTRAL")


def test_dealing_range():
    _, swings = _setup()
    assert dealing_range(swings) == (9, 12)
    assert dealing_range([]) is None


def test_dealing_range_inverted_returns_none():
    t = None
    swings = [SwingPoint(0, t, 10, True), SwingPoint(1, t, 11, False)]
    assert dealing_range(swings) is None
