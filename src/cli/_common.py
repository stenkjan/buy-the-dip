from __future__ import annotations

import os
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from bot_core.data import YFinanceSource
from bot_core.indicators import ema, resample_ohlc, rsi_wilder
from bot_core.types import AssetData
from strategies.buy_the_dip import BuyTheDipConfig

CONFIG_PATH = Path(os.environ.get("BTD_CONFIG", "config/default.toml"))


def load_config(path: Path | None = None) -> dict[str, Any]:
    with (path or CONFIG_PATH).open("rb") as f:
        return tomllib.load(f)


def build_strategy_config(cfg: dict[str, Any]) -> BuyTheDipConfig:
    s = cfg.get("strategy", {}).get("buy_the_dip", {})
    return BuyTheDipConfig(
        rsi_threshold_stufe1=float(s.get("rsi_threshold_stufe1", 30.0)),
        rsi_threshold_stufe2=float(s.get("rsi_threshold_stufe2", 30.0)),
        rsi_threshold_stufe3=float(s.get("rsi_threshold_stufe3", 30.0)),
        rsi_threshold_stufe1_liberal=float(s.get("rsi_threshold_stufe1_liberal", 35.0)),
        rsi_threshold_stufe2_liberal=float(s.get("rsi_threshold_stufe2_liberal", 30.5)),
        rsi_threshold_stufe3_liberal=float(s.get("rsi_threshold_stufe3_liberal", 32.0)),
        liberal=bool(s.get("liberal", True)),
        macro_reclaim_window_weeks=int(s.get("macro_reclaim_window_weeks", 8)),
    )


def build_history(
    symbol: str, config: BuyTheDipConfig, bars: int = 500
) -> list[dict[str, Any]] | None:
    """Per-bar daily history for the dashboard charts.

    Returns the last ``bars`` daily rows with the indicator series a trader
    sees in TradingView: close, EMA200 (daily & weekly) and RSI (1D & 1W).

    Each row also carries a coarse ``stufe`` (1/2/3 from price vs the two
    EMA200s) and a ``triggered`` flag. The flag is a chart-overlay
    approximation: it tests the *daily* RSI for Stufe 1/2 and the *weekly* RSI
    for Stufe 3, against the same thresholds the live strategy uses (ignoring
    the contextual macro-reclaim relaxation). The precise 12H-RSI signal
    timeline is a separate concern (roadmap phase 5c); this only needs to make
    historic dips visible as markers.
    """
    src = YFinanceSource()
    daily = src.fetch(symbol, "1d")
    if daily.empty or len(daily) < 250:
        print(f"warning: not enough daily data for {symbol}", file=sys.stderr)
        return None
    weekly = resample_ohlc(daily, "1W")

    close = daily["close"]
    ema_d = ema(close, 200)
    ema_w = ema(weekly["close"], 200).reindex(daily.index, method="ffill")
    rsi_d = rsi_wilder(close, 14)
    rsi_w = rsi_wilder(weekly["close"], 14).reindex(daily.index, method="ffill")

    df = pd.DataFrame(
        {
            "close": close,
            "ema200_daily": ema_d,
            "ema200_weekly": ema_w,
            "rsi_1d": rsi_d,
            "rsi_1w": rsi_w,
        },
        index=daily.index,
    ).dropna(subset=["ema200_daily", "ema200_weekly"]).tail(bars)

    above_d = df["close"] > df["ema200_daily"]
    above_w = df["close"] > df["ema200_weekly"]
    stufe = pd.Series(3, index=df.index)
    stufe = stufe.mask(above_w, 2).mask(above_d, 1)

    thr2 = config.rsi_threshold_stufe2_liberal if config.liberal else config.rsi_threshold_stufe2
    thr3 = config.rsi_threshold_stufe3_liberal if config.liberal else config.rsi_threshold_stufe3
    thresholds = {1: config.rsi_threshold_stufe1, 2: thr2, 3: thr3}
    rsi_used = df["rsi_1d"].where(stufe != 3, df["rsi_1w"])
    triggered = rsi_used <= stufe.map(thresholds)

    rows: list[dict[str, Any]] = []
    for ts, row in df.iterrows():
        rows.append(
            {
                "timestamp": ts.isoformat(),
                "close": float(row["close"]),
                "ema200_daily": float(row["ema200_daily"]),
                "ema200_weekly": float(row["ema200_weekly"]),
                "rsi_1d": float(row["rsi_1d"]) if pd.notna(row["rsi_1d"]) else None,
                "rsi_1w": float(row["rsi_1w"]) if pd.notna(row["rsi_1w"]) else None,
                "stufe": int(stufe.loc[ts]),
                "triggered": bool(triggered.loc[ts]),
            }
        )
    return rows


def snapshot_asset(symbol: str, history_bars: int = 60) -> AssetData | None:
    """Live snapshot of an asset. Returns None if insufficient daily history.

    `history_bars` is the number of recent daily bars (with EMA columns) attached
    to AssetData.history, used by strategies that need a lookback window
    (e.g. buy_the_dip's macro_reclaim detection).
    """
    src = YFinanceSource()
    daily = src.fetch(symbol, "1d")
    hourly = src.fetch(symbol, "1h")
    if daily.empty or len(daily) < 250:
        print(f"warning: not enough daily data for {symbol}", file=sys.stderr)
        return None
    weekly = resample_ohlc(daily, "1W")
    h12 = resample_ohlc(hourly, "12h") if not hourly.empty else daily

    ema_d = ema(daily["close"], 200)
    ema_w = ema(weekly["close"], 200).reindex(daily.index, method="ffill")
    history = pd.DataFrame(
        {"close": daily["close"], "ema200_daily": ema_d, "ema200_weekly": ema_w},
        index=daily.index,
    ).dropna().tail(history_bars)

    last = daily.iloc[-1]
    ts = daily.index[-1]
    return AssetData(
        symbol=symbol,
        timestamp=ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else datetime.now(UTC),
        last_close=float(last["close"]),
        ema200_daily=float(ema_d.iloc[-1]),
        ema200_weekly=float(ema_w.iloc[-1]),
        rsi_12h=float(rsi_wilder(h12["close"], 14).iloc[-1]),
        rsi_1d=float(rsi_wilder(daily["close"], 14).iloc[-1]),
        rsi_1w=float(rsi_wilder(weekly["close"], 14).iloc[-1]),
        history=history,
    )
