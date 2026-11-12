import pandas as pd
import pytest

import smc_engine as smc
from smc_engine import Direction, SMCConfig, StructureBreak, StructureEvent, ZoneKind


def test_full_pipeline_finds_everything(random_walk):
    a = smc.analyze(random_walk, symbol="XAUUSD", timeframe="M15")
    assert a.swings and a.minor_swings and a.breaks and a.liquidity and a.zones
    assert a.trend in ("BULLISH", "BEARISH")
    assert a.atr > 0 and 0 <= a.rsi <= 100
    assert a.dealing is not None and a.dealing[0] < a.dealing[1]
    assert {z.kind for z in a.zones} >= {ZoneKind.ORDER_BLOCK, ZoneKind.FVG}
    assert all(z.symbol == "XAUUSD" and z.timeframe == "M15" for z in a.zones)


def test_zones_are_pruned(random_walk):
    cfg = SMCConfig(max_zones_per_kind=3, zone_max_age_bars=100)
    a = smc.analyze(random_walk, cfg)
    n = len(random_walk)
    assert all(not z.invalidated and n - z.index <= 100 for z in a.zones)
    for kind in ZoneKind:
        assert sum(z.kind == kind for z in a.zones) <= 3
    assert [z.index for z in a.zones] == sorted(z.index for z in a.zones)
    assert a.active_zones == a.zones


def test_short_input_returns_empty(random_walk):
    a = smc.analyze(random_walk.head(20))
    assert a.zones == [] and a.swings == [] and a.trend == "NEUTRAL"
    assert len(a.df) == 20


def test_input_formats_give_same_result(random_walk):
    base = smc.analyze(random_walk).zones_frame()
    upper = random_walk.rename(columns=str.upper)
    indexed = random_walk.set_index("time")
    pd.testing.assert_frame_equal(smc.analyze(upper).zones_frame(), base)
    pd.testing.assert_frame_equal(smc.analyze(indexed).zones_frame(), base)


def test_frames(random_walk):
    a = smc.analyze(random_walk)
    assert len(a.swings_frame()) == len(a.swings)
    assert list(a.breaks_frame().columns) == ["index", "time", "event", "direction", "level"]
    zf = a.zones_frame()
    assert len(zf) == len(a.zones) and set(zf["kind"]) <= {"OB", "FVG", "BB"}
    assert len(a.liquidity_frame()) == len(a.liquidity)
    assert smc.Analysis().zones_frame().empty


def test_score_zone_bounds_and_notes(random_walk):
    a = smc.analyze(random_walk)
    for z in a.zones:
        score, notes = smc.score_zone(z, a, {"H1": "BULLISH", "H4": "BEARISH"})
        assert 0 <= score <= 100
        assert notes and all(isinstance(n, str) for n in notes)


def test_score_rewards_alignment(random_walk):
    a = smc.analyze(random_walk)
    z = a.zones[-1]
    want = z.direction.value
    against = "BEARISH" if want == "BULLISH" else "BULLISH"
    aligned, _ = smc.score_zone(z, a, {"H1": want, "H4": want})
    opposed, _ = smc.score_zone(z, a, {"H1": against, "H4": against})
    assert aligned - opposed == 40 or aligned == 100 or opposed == 0


def test_htf_aligned():
    bull = Direction.BULLISH
    assert smc.htf_aligned(bull, {"H1": "BULLISH", "H4": "NEUTRAL"})
    assert not smc.htf_aligned(bull, {"H1": "BULLISH", "H4": "BEARISH"})
    assert not smc.htf_aligned(bull, {"H1": "NEUTRAL"})
    assert smc.htf_aligned(bull, {"H1": "BULLISH", "H4": "BEARISH"}, mode="first")
    assert not smc.htf_aligned(bull, {}, mode="first")
    with pytest.raises(ValueError):
        smc.htf_aligned(bull, {}, mode="nope")


def test_detect_ltf_choch():
    df = pd.DataFrame({"time": pd.date_range("2026-01-01", periods=30, freq="min")})
    a = smc.Analysis(df=df, breaks=[
        StructureBreak(StructureEvent.CHOCH, Direction.BULLISH, 1.0, df["time"][25], 25),
    ])
    assert smc.detect_ltf_choch(a, Direction.BULLISH)
    assert not smc.detect_ltf_choch(a, Direction.BEARISH)
    assert not smc.detect_ltf_choch(a, Direction.BULLISH, within_bars=3)
    assert not smc.detect_ltf_choch(smc.Analysis(), Direction.BULLISH)


def test_building_blocks_compose(random_walk):
    data = smc.prepare(random_walk)
    swings = smc.find_swings(data, lookback=3)
    breaks, _ = smc.detect_structure(data, swings, confirm_lag=3)
    obs = smc.detect_order_blocks(data, breaks, atr_val=smc.atr(data))
    assert obs and all(ob.linked_bos in breaks for ob in obs)
