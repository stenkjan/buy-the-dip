from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from bot_core.alerts import ConsoleNotifier, Notifier, TelegramNotifier
from bot_core.state import FileStateStore
from strategies.buy_the_dip import get_strategy

from ._common import build_strategy_config, load_config, snapshot_asset


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="btd", description="Buy-the-dip signal bot")
    parser.add_argument("--mode", choices=["scheduled", "manual"], default="scheduled")
    parser.add_argument("--asset", default="both", help="symbol, e.g. ^NDX, ^GSPC, or 'both'")
    parser.add_argument(
        "--force-alert", action="store_true", help="send alert even if not triggered"
    )
    args = parser.parse_args(argv)

    cfg = load_config()
    assets = cfg["data"]["assets"] if args.asset == "both" else [args.asset]
    strategy = get_strategy(build_strategy_config(cfg))
    notifiers = _build_notifiers(cfg["alerts"]["channels"])
    state = FileStateStore(Path(cfg["alerts"]["idempotency_dir"]) / "alerts.json")

    exit_code = 0
    for symbol in assets:
        data = snapshot_asset(symbol)
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
