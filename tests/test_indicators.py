import pandas as pd
import pytest

from smc_engine import atr, ema_bias, rsi, trading_session

from .conftest import from_closes, make_df


def test_atr_constant_range():
    df = make_df([(10, 11, 9, 10)] * 30)
    assert atr(df) == pytest.approx(2.0)


def test_atr_short_data_uses_mean_range():
    assert atr(make_df([(10, 11, 9, 10), (10, 13, 9, 10)])) == pytest.approx(3.0)


def test_rsi_extremes():
    assert rsi(from_closes(list(range(1, 40)))) == 100.0
    assert rsi(from_closes([5.0] * 40)) == 50.0
    assert rsi(from_closes([1, 2])) == 50.0
    assert rsi(from_closes(list(range(40, 1, -1)))) == pytest.approx(0.0)


def test_ema_bias():
    assert ema_bias(from_closes([float(x) for x in range(100)])) == "BULLISH"
    assert ema_bias(from_closes([float(x) for x in range(100, 0, -1)])) == "BEARISH"
    assert ema_bias(from_closes([1.0] * 10)) == "NEUTRAL"


@pytest.mark.parametrize(("utc", "expected"), [
    ("2026-07-01 07:30", "London"),            # 08:30 BST
    ("2026-01-15 07:30", "Asia"),              # 07:30 GMT, London not open yet
    ("2026-01-15 09:00", "London"),
    ("2026-01-15 14:00", "London-NY Overlap"),
    ("2026-01-15 18:00", "New York"),
    ("2026-01-15 03:00", "Asia"),
    ("2026-01-15 23:00", "Sydney/Late NY"),
])
def test_trading_session(utc, expected):
    assert trading_session(pd.Timestamp(utc)) == expected


def test_trading_session_timezone_aware():
    assert trading_session(pd.Timestamp("2026-01-15 10:00", tz="Asia/Jakarta")) == "Asia"
