from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from bot_core.indicators import ema, resample_ohlc, rsi_wilder
from bot_core.signals.base import Strategy
from bot_core.types import AssetData, Signal


@dataclass
class BacktestResult:
    symbol: str
    signals: list[Signal]
    indicators: pd.DataFrame  # daily index with close/ema_d/ema_w/rsi_12h/rsi_1d/rsi_1w


def _compute_indicators(daily: pd.DataFrame, hourly: pd.DataFrame | None) -> pd.DataFrame:
    out = pd.DataFrame(index=daily.index)
    out["close"] = daily["close"]
    out["ema_d"] = ema(daily["close"], 200)
    weekly = resample_ohlc(daily, "1W")
    out["ema_w"] = ema(weekly["close"], 200).reindex(daily.index, method="ffill")
    out["rsi_1d"] = rsi_wilder(daily["close"], 14)
    out["rsi_1w"] = rsi_wilder(weekly["close"], 14).reindex(daily.index, method="ffill")
    if hourly is not None and not hourly.empty:
        h12 = resample_ohlc(hourly, "12h")
        rsi_12h = rsi_wilder(h12["close"], 14).reindex(daily.index, method="ffill")
        out["rsi_12h"] = rsi_12h
    else:
        out["rsi_12h"] = out["rsi_1d"]  # fallback when intraday history is unavailable
    return out


def run_backtest(
    symbol: str,
    daily: pd.DataFrame,
    strategy: Strategy,
    hourly: pd.DataFrame | None = None,
    on_signal: Callable[[Signal], None] | None = None,
) -> BacktestResult:
    ind = _compute_indicators(daily, hourly).dropna()
    signals: list[Signal] = []
    for ts, row in ind.iterrows():
        data = AssetData(
            symbol=symbol,
            timestamp=ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts,
            last_close=float(row["close"]),
            ema200_daily=float(row["ema_d"]),
            ema200_weekly=float(row["ema_w"]),
            rsi_12h=float(row["rsi_12h"]),
            rsi_1d=float(row["rsi_1d"]),
            rsi_1w=float(row["rsi_1w"]),
        )
        sig = strategy.evaluate(data)
        if sig.triggered:
            signals.append(sig)
            if on_signal is not None:
                on_signal(sig)
    return BacktestResult(symbol=symbol, signals=signals, indicators=ind)
