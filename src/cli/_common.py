from __future__ import annotations

import os
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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


def snapshot_asset(symbol: str) -> AssetData | None:
    src = YFinanceSource()
    daily = src.fetch(symbol, "1d")
    hourly = src.fetch(symbol, "1h")
    if daily.empty or len(daily) < 250:
        print(f"warning: not enough daily data for {symbol}", file=sys.stderr)
        return None
    weekly = resample_ohlc(daily, "1W")
    h12 = resample_ohlc(hourly, "12h") if not hourly.empty else daily

    last = daily.iloc[-1]
    ts = daily.index[-1]
    return AssetData(
        symbol=symbol,
        timestamp=ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else datetime.now(UTC),
        last_close=float(last["close"]),
        ema200_daily=float(ema(daily["close"], 200).iloc[-1]),
        ema200_weekly=float(ema(weekly["close"], 200).iloc[-1]),
        rsi_12h=float(rsi_wilder(h12["close"], 14).iloc[-1]),
        rsi_1d=float(rsi_wilder(daily["close"], 14).iloc[-1]),
        rsi_1w=float(rsi_wilder(weekly["close"], 14).iloc[-1]),
    )
