import pytest

from smc_engine import SwingKind, find_swings

from .conftest import make_df


def _df():
    hl = [(10, 9), (12, 10), (11, 9.5), (13, 10.5), (12, 8), (12.5, 9), (11, 8.5)]
    return make_df([((h + l) / 2, h, l, (h + l) / 2) for h, l in hl])


def test_detects_and_classifies_swings():
    swings = find_swings(_df(), lookback=1)
    got = [(s.index, s.price, s.is_high, s.kind) for s in swings]
    assert got == [
        (1, 12, True, SwingKind.H),
        (2, 9.5, False, SwingKind.L),
        (3, 13, True, SwingKind.HH),
        (4, 8, False, SwingKind.LL),
        (5, 12.5, True, SwingKind.LH),
    ]


def test_unconfirmed_tail_is_not_a_swing():
    swings = find_swings(_df(), lookback=1)
    assert all(s.index < 6 for s in swings)


def test_equal_highs_only_first_counts():
    df = make_df([(1, 1, 0, 1), (1, 3, 0.5, 1), (1, 3, 0.5, 1), (1, 1, 0, 1)])
    highs = [s.index for s in find_swings(df, lookback=1) if s.is_high]
    assert highs == [1]


def test_invalid_lookback():
    with pytest.raises(ValueError):
        find_swings(_df(), lookback=0)
