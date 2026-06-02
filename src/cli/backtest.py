from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from bot_core.backtest import forward_returns, run_backtest, summarize
from bot_core.data import YFinanceSource
from strategies.buy_the_dip import BuyTheDipConfig, get_strategy


def _parse_date(s: str) -> datetime:
    return datetime.fromisoformat(s)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="btd-backtest", description="Replay strategy over history")
    p.add_argument("--asset", required=True, help="symbol, e.g. ^NDX, ^GSPC")
    p.add_argument("--start", type=_parse_date, default=datetime(2000, 1, 1))
    p.add_argument("--end", type=_parse_date, default=None)
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("backtest"),
        help="directory for <asset>.csv (signals) and <asset>.summary.json",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="use strict thresholds only (default: liberal enabled)",
    )
    args = p.parse_args(argv)

    src = YFinanceSource()
    daily = src.fetch(args.asset, "1d", start=args.start, end=args.end)
    if daily.empty or len(daily) < 250:
        print(f"error: insufficient daily history for {args.asset}", file=sys.stderr)
        return 2

    strategy = get_strategy(BuyTheDipConfig(liberal=not args.strict))
    result = run_backtest(args.asset, daily, strategy, hourly=None)
    signals_df = forward_returns(result.signals, result.indicators)
    stats = summarize(signals_df)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    safe = args.asset.lstrip("^").lower()
    csv_path = args.output_dir / f"{safe}.csv"
    summary_path = args.output_dir / f"{safe}.summary.json"
    signals_df.to_csv(csv_path, index=False)
    summary_path.write_text(json.dumps(stats, indent=2))

    print(f"{args.asset}: {stats['total']} signals over {len(result.indicators)} bars")
    print(f"  per stufe: {stats['per_stufe']}")
    for horizon, s in stats["forward_returns"].items():
        print(
            f"  {horizon}: n={s['n']} mean={s['mean']:+.2%} "
            f"median={s['median']:+.2%} win={s['win_rate']:.0%}"
        )
    print(f"wrote {csv_path} and {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
