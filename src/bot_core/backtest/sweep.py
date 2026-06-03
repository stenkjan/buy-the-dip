"""Parameter sweep — replay the strategy over a grid of threshold variations.

Suggestions only: this surfaces how alternative thresholds would have performed
historically so a human can compare. It never mutates a bot's config itself.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from strategies.buy_the_dip import BuyTheDipConfig, get_strategy

from .runner import forward_returns, run_backtest, summarize

# Default grid: vary the (shared) strict RSI threshold around the baseline 30.
DEFAULT_GRID: list[dict[str, Any]] = [
    {"rsi_threshold_stufe1": t, "rsi_threshold_stufe2": t, "rsi_threshold_stufe3": t,
     "liberal": False}
    for t in (28.0, 30.0, 32.0)
]


def _finite(x: float | None) -> float | None:
    return x if (x is not None and math.isfinite(x)) else None


def run_sweep(
    symbol: str,
    daily: pd.DataFrame,
    grid: list[dict[str, Any]] | None = None,
    *,
    horizon: str = "fwd_90d",
) -> list[dict[str, Any]]:
    """Run the backtest once per grid entry; return results ranked by mean
    forward return at ``horizon`` (best first). Each grid entry is a partial
    config dict merged onto BuyTheDipConfig defaults via from_dict.
    """
    grid = grid if grid is not None else DEFAULT_GRID
    results: list[dict[str, Any]] = []
    for params in grid:
        cfg = BuyTheDipConfig.from_dict(params)
        res = run_backtest(symbol, daily, get_strategy(cfg), hourly=None)
        stats = summarize(forward_returns(res.signals, res.indicators))
        fwd = stats["forward_returns"].get(horizon, {})
        results.append({
            "params": params,
            "total_signals": stats["total"],
            "per_stufe": stats["per_stufe"],
            "mean_forward_return": _finite(fwd.get("mean")),
            "win_rate": _finite(fwd.get("win_rate")),
            "n_forward": fwd.get("n", 0),
            "horizon": horizon,
        })

    # Rank best-first; entries with no forward data sort last.
    def _rank(r: dict[str, Any]) -> tuple[bool, float]:
        m = r["mean_forward_return"]
        return (m is None, -(m or 0.0))

    results.sort(key=_rank)
    return results
