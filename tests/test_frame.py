import pandas as pd
import pytest

from smc_engine._frame import prepare


def _base():
    return pd.DataFrame({
        "Time": pd.date_range("2026-01-01", periods=3, freq="h"),
        "Open": [1, 2, 3], "High": [2, 3, 4], "Low": [0, 1, 2], "Close": [1.5, 2.5, 3.5],
    })


def test_lowercases_columns_and_casts_float():
    out = prepare(_base())
    assert list(out.columns[:5]) == ["time", "open", "high", "low", "close"]
    assert out["open"].dtype == float


def test_accepts_datetime_index():
    df = _base().set_index("Time")
    out = prepare(df)
    assert "time" in out.columns
    assert list(out.index) == [0, 1, 2]


def test_timezone_aware_converted_to_naive_utc():
    df = _base()
    df["Time"] = df["Time"].dt.tz_localize("Asia/Jakarta")
    out = prepare(df)
    assert out["time"].dt.tz is None
    assert out["time"].iloc[0] == pd.Timestamp("2025-12-31 17:00")


def test_missing_column_raises():
    with pytest.raises(ValueError, match="close"):
        prepare(_base().drop(columns="Close"))


def test_missing_time_raises():
    with pytest.raises(ValueError, match="time"):
        prepare(_base().drop(columns="Time"))


def test_unsorted_raises():
    with pytest.raises(ValueError, match="sorted"):
        prepare(_base().iloc[::-1])


def test_does_not_mutate_input():
    df = _base()
    prepare(df)
    assert "Open" in df.columns
