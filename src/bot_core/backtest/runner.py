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


_FORWARD_DAYS = (30, 90, 180, 365)


def forward_returns(
    signals: list[Signal],
    indicators: pd.DataFrame,
    horizons_days: tuple[int, ...] = _FORWARD_DAYS,
) -> pd.DataFrame:
    """One row per signal with forward returns at the given calendar-day horizons.

    Returns are computed against the nearest available bar at or after
    `signal.timestamp + horizon` to avoid look-ahead. A NaN means the horizon
    extends past the available data.
    """
    if not signals:
        return pd.DataFrame()

    closes = indicators["close"]
    rows = []
    for s in signals:
        ts = pd.Timestamp(s.timestamp)
        row: dict[str, object] = {
            "timestamp": ts.isoformat(),
            "symbol": s.symbol,
            "stufe": s.stufe,
            "rsi_value": s.rsi_value,
            "rsi_threshold": s.rsi_threshold,
            "price": s.price,
            "tranche_lo": s.tranche_pct_range[0] if s.tranche_pct_range else None,
            "tranche_hi": s.tranche_pct_range[1] if s.tranche_pct_range else None,
        }
        for h in horizons_days:
            target = ts + pd.Timedelta(days=h)
            future = closes.loc[closes.index >= target]
            row[f"fwd_{h}d"] = float(future.iloc[0] / s.price - 1.0) if len(future) else None
        rows.append(row)
    return pd.DataFrame(rows)


def summarize(signals_df: pd.DataFrame) -> dict[str, object]:
    """Aggregate stats from a forward-returns DataFrame produced by `forward_returns`."""
    if signals_df.empty:
        return {"total": 0, "per_stufe": {}, "forward_returns": {}}

    per_stufe = signals_df.groupby("stufe").size().to_dict()
    fwd_cols = [c for c in signals_df.columns if c.startswith("fwd_")]
    fwd_stats: dict[str, dict[str, float]] = {}
    for c in fwd_cols:
        series = signals_df[c].dropna()
        if series.empty:
            continue
        fwd_stats[c] = {
            "n": int(series.size),
            "mean": float(series.mean()),
            "median": float(series.median()),
            "win_rate": float((series > 0).mean()),
        }
    return {
        "total": len(signals_df),
        "per_stufe": {int(k): int(v) for k, v in per_stufe.items()},
        "forward_returns": fwd_stats,
    }
