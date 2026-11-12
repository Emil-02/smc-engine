import pytest

import smc_engine as smc

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")


def test_plot_returns_axes(random_walk):
    from smc_engine.plot import plot

    a = smc.analyze(random_walk, symbol="XAUUSD", timeframe="M15")
    ax = plot(a, last=150)
    assert "XAUUSD M15" in ax.get_title()
    assert ax.patches


def test_plot_requires_data():
    from smc_engine.plot import plot

    with pytest.raises(ValueError):
        plot(smc.Analysis())
