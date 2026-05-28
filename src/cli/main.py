from __future__ import annotations

import argparse
import os
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from bot_core.alerts import ConsoleNotifier, Notifier, TelegramNotifier
from bot_core.data import YFinanceSource
from bot_core.indicators import ema, resample_ohlc, rsi_wilder
from bot_core.state import FileStateStore
from bot_core.types import AssetData
from strategies.buy_the_dip import BuyTheDipConfig, get_strategy

CONFIG_PATH = Path(os.environ.get("BTD_CONFIG", "config/default.toml"))


def _load_config() -> dict:
    with CONFIG_PATH.open("rb") as f:
        return tomllib.load(f)


def _build_notifiers(channels: list[str]) -> list[Notifier]:
    out: list[Notifier] = []
    for ch in channels:
        if ch == "console":
            out.append(ConsoleNotifier())
        elif ch == "telegram":
            out.append(TelegramNotifier())
        else:
            print(f"warning: unknown notifier '{ch}' — skipping", file=sys.stderr)
    return out


def _snapshot(symbol: str) -> AssetData | None:
    src = YFinanceSource()
    daily = src.fetch(symbol, "1d")
    hourly = src.fetch(symbol, "1h")
    if daily.empty or len(daily) < 250:
        print(f"warning: not enough daily data for {symbol}", file=sys.stderr)
        return None
    weekly = resample_ohlc(daily, "1W")
    h12 = resample_ohlc(hourly, "12h") if not hourly.empty else daily

    ema_d = ema(daily["close"], 200).iloc[-1]
    ema_w = ema(weekly["close"], 200).iloc[-1]
    rsi_12h = rsi_wilder(h12["close"], 14).iloc[-1]
    rsi_1d = rsi_wilder(daily["close"], 14).iloc[-1]
    rsi_1w = rsi_wilder(weekly["close"], 14).iloc[-1]

    last = daily.iloc[-1]
    ts = daily.index[-1]
    return AssetData(
        symbol=symbol,
        timestamp=ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else datetime.now(UTC),
        last_close=float(last["close"]),
        ema200_daily=float(ema_d),
        ema200_weekly=float(ema_w),
        rsi_12h=float(rsi_12h),
        rsi_1d=float(rsi_1d),
        rsi_1w=float(rsi_1w),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="btd", description="Buy-the-dip signal bot")
    parser.add_argument("--mode", choices=["scheduled", "manual"], default="scheduled")
    parser.add_argument("--asset", default="both", help="symbol, e.g. ^NDX, ^GSPC, or 'both'")
    parser.add_argument(
        "--force-alert", action="store_true", help="send alert even if not triggered"
    )
    args = parser.parse_args(argv)

    cfg = _load_config()
    assets = cfg["data"]["assets"] if args.asset == "both" else [args.asset]

    strat_cfg = cfg.get("strategy", {}).get("buy_the_dip", {})
    strategy = get_strategy(
        BuyTheDipConfig(
            rsi_threshold_stufe1=float(strat_cfg.get("rsi_threshold_stufe1", 30.0)),
            rsi_threshold_stufe2=float(strat_cfg.get("rsi_threshold_stufe2", 30.0)),
            rsi_threshold_stufe3=float(strat_cfg.get("rsi_threshold_stufe3", 30.0)),
            rsi_threshold_stufe1_liberal=float(strat_cfg.get("rsi_threshold_stufe1_liberal", 35.0)),
            rsi_threshold_stufe2_liberal=float(strat_cfg.get("rsi_threshold_stufe2_liberal", 30.5)),
            rsi_threshold_stufe3_liberal=float(strat_cfg.get("rsi_threshold_stufe3_liberal", 32.0)),
            liberal=bool(strat_cfg.get("liberal", True)),
            macro_reclaim_window_weeks=int(strat_cfg.get("macro_reclaim_window_weeks", 8)),
        )
    )

    notifiers = _build_notifiers(cfg["alerts"]["channels"])
    state = FileStateStore(Path(cfg["alerts"]["idempotency_dir"]) / "alerts.json")

    exit_code = 0
    for symbol in assets:
        data = _snapshot(symbol)
        if data is None:
            exit_code = 1
            continue
        signal = strategy.evaluate(data)
        key = f"{symbol}:{pd.Timestamp(signal.timestamp).floor('12h').isoformat()}:s{signal.stufe}"
        if not (signal.triggered or args.force_alert):
            print(
                f"{symbol}: no signal (stufe {signal.stufe}, "
                f"rsi={signal.rsi_value:.2f}, thr={signal.rsi_threshold:.2f})"
            )
            continue
        if state.already_alerted(key):
            print(f"{symbol}: signal already alerted ({key}) — skipping")
            continue
        for n in notifiers:
            n.send(signal)
        state.mark_alerted(key)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
