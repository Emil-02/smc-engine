import pandas as pd

from smc_engine import (
    Direction,
    StructureBreak,
    StructureEvent,
    Zone,
    ZoneKind,
    detect_breakers,
    detect_fvg,
    detect_order_blocks,
    price_position_label,
    tag_premium_discount,
    update_zone_lifecycle,
)

from .conftest import make_df


def test_bullish_fvg():
    df = make_df([(10, 11, 9.5, 10.8), (10.8, 14, 10.7, 13.8), (13.8, 15, 12, 14.5)])
    zones = detect_fvg(df, atr_val=1.0, timeframe="M15", symbol="XAUUSD")
    assert len(zones) == 1
    z = zones[0]
    assert (z.kind, z.direction, z.top, z.bottom, z.index) == (
        ZoneKind.FVG, Direction.BULLISH, 12, 11, 1)
    assert z.displacement == 1.0
    assert z.label == "FVG+ M15"


def test_bearish_fvg_and_min_gap():
    df = make_df([(15, 15, 13, 13.2), (13.2, 13.3, 10, 10.1), (10.1, 12.5, 9.5, 9.8)])
    zones = detect_fvg(df, atr_val=1.0)
    assert [(z.direction, z.top, z.bottom) for z in zones] == [(Direction.BEARISH, 13, 12.5)]
    assert detect_fvg(df, atr_val=1.0, min_gap_atr=0.6) == []


def _ob_df():
    return make_df([
        (10, 10.5, 9.5, 10.2),
        (10.2, 10.4, 9.0, 9.2),   # last bearish candle -> bullish OB
        (9.2, 11, 9.1, 10.9),
        (10.9, 12.5, 10.8, 12.4),  # breaking candle
        (12.4, 12.5, 10.3, 11),    # taps the OB (touch 1)
        (11, 11.2, 10.0, 10.5),    # touch 2
        (10.5, 10.6, 8.5, 8.8),    # closes below the OB -> invalid / breaker
    ])


def _brk(df, i, direction=Direction.BULLISH):
    return StructureBreak(StructureEvent.BOS, direction, 11, df["time"][i], i)


def test_order_block_from_break():
    df = _ob_df()
    obs = detect_order_blocks(df, [_brk(df, 3)], atr_val=1.0)
    assert len(obs) == 1
    ob = obs[0]
    assert (ob.index, ob.top, ob.bottom, ob.direction) == (1, 10.4, 9.0, Direction.BULLISH)
    assert round(ob.displacement, 6) == 3.4
    assert ob.linked_bos.break_index == 3


def test_order_block_needs_displacement():
    df = _ob_df()
    assert detect_order_blocks(df, [_brk(df, 3)], atr_val=1.0, displacement_atr_mult=4) == []


def test_order_block_deduplicated_keeps_strongest():
    df = _ob_df()
    obs = detect_order_blocks(df, [_brk(df, 2), _brk(df, 3)], atr_val=1.0)
    assert len(obs) == 1 and round(obs[0].displacement, 6) == 3.4


def test_bearish_order_block():
    df = make_df([
        (10, 10.5, 9.5, 10.3),
        (10.3, 11, 10.2, 10.9),   # last bullish candle -> bearish OB
        (10.9, 11, 9, 9.1),
        (9.1, 9.2, 7.5, 7.6),
    ])
    obs = detect_order_blocks(df, [_brk(df, 3, Direction.BEARISH)], atr_val=1.0)
    assert [(z.index, z.direction, z.top, z.bottom) for z in obs] == [
        (1, Direction.BEARISH, 11, 10.2)]


def test_breaker_flips_failed_order_block():
    df = _ob_df()
    obs = detect_order_blocks(df, [_brk(df, 3)], atr_val=1.0)
    breakers = detect_breakers(df, obs)
    assert [(z.kind, z.direction, z.index) for z in breakers] == [
        (ZoneKind.BREAKER, Direction.BEARISH, 6)]
    assert obs[0].invalidated


def test_lifecycle_touches_then_invalidates():
    df = _ob_df()
    ob = detect_order_blocks(df, [_brk(df, 3)], atr_val=1.0)[0]
    update_zone_lifecycle(df, [ob])
    assert ob.mitigated and ob.touches == 2 and ob.invalidated
    assert ob.mitigated_time == df["time"][4]


def _zone(direction, top, bottom):
    return Zone(ZoneKind.ORDER_BLOCK, direction, top, bottom, pd.Timestamp("2026-01-01"), 0)


def test_premium_discount_and_ote():
    deep = _zone(Direction.BULLISH, 125, 115)    # mid 120
    ote = _zone(Direction.BULLISH, 135, 125)     # mid 130
    supply = _zone(Direction.BEARISH, 175, 165)  # mid 170
    tag_premium_discount([deep, ote, supply], (100, 200))
    assert (deep.in_discount, deep.in_ote) == (True, False)
    assert (ote.in_discount, ote.in_ote) == (True, True)
    assert (supply.in_discount, supply.in_ote) == (False, True)


def test_premium_discount_without_range_is_noop():
    z = _zone(Direction.BULLISH, 2, 1)
    tag_premium_discount([z], None)
    assert z.in_discount is None


def test_price_position_label():
    assert price_position_label(175, (100, 200)) == "PREMIUM (75%)"
    assert price_position_label(130, (100, 200)) == "DISCOUNT (30%)"
    assert price_position_label(130, None) == "UNKNOWN"
