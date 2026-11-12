"""Optional matplotlib chart (``pip install smc-engine[plot]``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import Direction, ZoneKind

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from .engine import Analysis

_ZONE_COLORS = {
    (ZoneKind.ORDER_BLOCK, Direction.BULLISH): "#2e7d32",
    (ZoneKind.ORDER_BLOCK, Direction.BEARISH): "#c62828",
    (ZoneKind.FVG, Direction.BULLISH): "#64b5f6",
    (ZoneKind.FVG, Direction.BEARISH): "#ffb74d",
    (ZoneKind.BREAKER, Direction.BULLISH): "#9575cd",
    (ZoneKind.BREAKER, Direction.BEARISH): "#f06292",
}


def plot(analysis: Analysis, last: int | None = 200, ax: Axes | None = None,
         show_liquidity: bool = True) -> Axes:
    """Candles with active zones, BOS/CHoCH levels, swings and liquidity pools.

    ``last`` limits the chart to the most recent bars (``None`` = everything).
    The x axis is the bar index.
    """
    try:
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
    except ImportError as exc:  # pragma: no cover
        raise ImportError("plotting needs matplotlib: pip install 'smc-engine[plot]'") from exc

    if analysis.df is None or analysis.df.empty:
        raise ValueError("analysis has no data")
    df = analysis.df
    n = len(df)
    start = 0 if last is None else max(0, n - last)
    if ax is None:
        _, ax = plt.subplots(figsize=(14, 7))

    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    for i in range(start, n):
        color = "#26a69a" if c[i] >= o[i] else "#ef5350"
        ax.vlines(i, l[i], h[i], color=color, linewidth=0.8)
        ax.add_patch(Rectangle((i - 0.3, min(o[i], c[i])), 0.6, abs(c[i] - o[i]) or 1e-9,
                               color=color))

    for z in analysis.active_zones:
        if z.index < start:
            continue
        color = _ZONE_COLORS[(z.kind, z.direction)]
        ax.add_patch(Rectangle((z.index, z.bottom), n - z.index, z.height, color=color,
                               alpha=0.18 if z.mitigated else 0.3, linewidth=0))
        ax.text(z.index, z.top, z.kind.value, fontsize=7, color=color, va="bottom")

    for b in analysis.breaks:
        ref = b.swing_ref.index if b.swing_ref else b.break_index
        if b.break_index < start:
            continue
        color = "#2e7d32" if b.direction == Direction.BULLISH else "#c62828"
        style = "-" if b.event.value == "BOS" else "--"
        ax.hlines(b.broken_level, max(ref, start), b.break_index, colors=color,
                  linestyles=style, linewidth=1)
        ax.text(b.break_index, b.broken_level, b.event.value, fontsize=7, color=color)

    for s in analysis.swings:
        if s.index >= start:
            ax.annotate(s.kind.value, (s.index, s.price), fontsize=6, ha="center",
                        va="bottom" if s.is_high else "top", color="#555")

    if show_liquidity:
        for p in analysis.liquidity:
            if p.index >= start:
                ax.hlines(p.price, p.index, n, colors="#999", linestyles=":", linewidth=0.8)
                ax.text(n, p.price, p.label + (" (swept)" if p.swept else ""), fontsize=6,
                        va="center", color="#666")

    title = " ".join(x for x in (analysis.symbol, analysis.timeframe) if x)
    ax.set_title(f"{title} trend: {analysis.trend}".strip())
    ax.set_xlim(start - 1, n + 8)
    ax.grid(alpha=0.2)
    return ax
