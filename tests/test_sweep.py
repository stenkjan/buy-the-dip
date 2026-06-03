from __future__ import annotations

import numpy as np
import pandas as pd

from bot_core.backtest import DEFAULT_GRID, run_sweep


def _daily(n: int = 1600) -> pd.DataFrame:
    idx = pd.date_range("2018-01-01", periods=n, freq="D", tz="UTC")
    close = np.linspace(100.0, 320.0, n)
    close[-40:] = close[-41] * 0.55  # crash → triggers
    return pd.DataFrame(
        {"open": close, "high": close, "low": close, "close": close,
         "volume": [1_000_000] * n},
        index=idx,
    )


def test_sweep_returns_one_result_per_grid_entry_ranked():
    results = run_sweep("^NDX", _daily())
    assert len(results) == len(DEFAULT_GRID)
    for r in results:
        assert {"params", "total_signals", "mean_forward_return", "win_rate", "horizon"} <= r.keys()
        assert r["horizon"] == "fwd_90d"
    # ranked best-first: non-null mean returns are non-increasing, nulls last
    means = [r["mean_forward_return"] for r in results]
    non_null = [m for m in means if m is not None]
    assert non_null == sorted(non_null, reverse=True)
    # higher threshold should fire at least as many signals as a lower one
    by_thr = {r["params"]["rsi_threshold_stufe1"]: r["total_signals"] for r in results}
    assert by_thr[32.0] >= by_thr[28.0]


def test_sweep_custom_grid():
    grid = [{"rsi_threshold_stufe1": 30, "liberal": False}]
    results = run_sweep("^NDX", _daily(), grid)
    assert len(results) == 1
    assert results[0]["params"] == grid[0]
