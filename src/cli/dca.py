"""Compare the buy-the-dip strategy against dollar-cost averaging.

    python -m cli.dca --asset ^NDX --start 2000-01-01 --monthly 1000
    python -m cli.dca --csv prices.csv --symbol ^NDX     # offline / no network

The CSV path lets you run fully offline: provide a file with at least `date`
and `close` columns (daily bars). This is the path to use when the environment
has no market-data network access or API key.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from bot_core.backtest import compare_dca, run_backtest
from bot_core.data import StooqSource, YFinanceSource
from strategies.buy_the_dip import BuyTheDipConfig, get_strategy


def _parse_date(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]
    if "date" not in df.columns or "close" not in df.columns:
        raise ValueError("CSV must have at least 'date' and 'close' columns")
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.set_index("date").sort_index()
    for col in ("open", "high", "low", "volume"):
        if col not in df.columns:
            df[col] = df["close"]
    return df[["open", "high", "low", "close", "volume"]]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="btd-dca", description="Strategy vs dollar-cost-averaging performance + Sharpe"
    )
    p.add_argument("--asset", help="symbol to fetch, e.g. ^NDX, ^GSPC")
    p.add_argument(
        "--source",
        choices=["stooq", "yfinance"],
        default="stooq",
        help="data provider for --asset (default: stooq — single host, no API key)",
    )
    p.add_argument("--csv", type=Path, help="local OHLC CSV (date,close[,open,high,low,volume])")
    p.add_argument("--symbol", help="label to use with --csv (defaults to the file stem)")
    p.add_argument("--start", type=_parse_date, default=datetime(2000, 1, 1))
    p.add_argument("--end", type=_parse_date, default=None)
    p.add_argument(
        "--monthly", type=float, default=1000.0, help="monthly contribution (default 1000)"
    )
    p.add_argument("--risk-free", type=float, default=0.0, help="annual risk-free rate, e.g. 0.02")
    p.add_argument("--strict", action="store_true", help="strict thresholds only")
    p.add_argument("--output", type=Path, help="optional path to write the comparison JSON")
    args = p.parse_args(argv)

    if not args.asset and not args.csv:
        print("error: pass either --asset (network) or --csv (offline)", file=sys.stderr)
        return 2

    if args.csv:
        daily = _load_csv(args.csv)
        symbol = args.symbol or args.csv.stem
        daily = daily.loc[(daily.index >= pd.Timestamp(args.start, tz="UTC"))]
        if args.end is not None:
            daily = daily.loc[daily.index <= pd.Timestamp(args.end, tz="UTC")]
    else:
        symbol = args.asset
        source = StooqSource() if args.source == "stooq" else YFinanceSource()
        daily = source.fetch(args.asset, "1d", start=args.start, end=args.end)

    if daily.empty or len(daily) < 250:
        print(f"error: insufficient daily history for {symbol}", file=sys.stderr)
        return 2

    strategy = get_strategy(BuyTheDipConfig(liberal=not args.strict))
    result = run_backtest(symbol, daily, strategy, hourly=None)
    report = compare_dca(
        symbol,
        result.indicators["close"],
        result.signals,
        monthly_contribution=args.monthly,
        risk_free_annual=args.risk_free,
    )

    text = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
