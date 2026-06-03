"""Historical signal timeline.

Replays the strategy over the last ~20 years and records every *triggered*
bar with its Stufe, RSI, threshold, price and forward returns. Unlike the
coarse trigger overlay baked into ``cli.snapshot``'s ``history.json`` (which
vectorises a daily-RSI approximation), this uses the real per-bar strategy
evaluation — same engine as ``cli.backtest`` — including macro-reclaim
detection and the correct per-Stufe RSI.

Writes ``<output-dir>/<asset>.timeline.json``; the ``history-timeline``
workflow publishes it to the ``data`` branch under ``history/<asset>.json``
for the dashboard's timeline view.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bot_core.backtest import forward_returns, run_backtest, summarize
from bot_core.data import YFinanceSource
from strategies.buy_the_dip import BuyTheDipConfig, get_strategy

SCHEMA_VERSION = 1


def _parse_date(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _json_safe(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def build_timeline(
    symbol: str, daily: Any, *, liberal: bool = True
) -> dict[str, Any]:
    """Run the backtest and shape the result into a dashboard timeline payload."""
    strategy = get_strategy(BuyTheDipConfig(liberal=liberal))
    # hourly=None on purpose: a 20-year window has no intraday history, and the
    # runner falls back to the daily RSI for the 12H slot rather than dropping
    # every pre-intraday bar.
    result = run_backtest(symbol, daily, strategy, hourly=None)
    signals_df = forward_returns(result.signals, result.indicators)
    stats = summarize(signals_df)

    signals = [] if signals_df.empty else signals_df.to_dict(orient="records")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "asset": symbol,
        "liberal": liberal,
        "n_bars": len(result.indicators),
        "summary": stats,
        "signals": signals,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="btd-history",
        description="Historical triggered-signal timeline for the dashboard",
    )
    p.add_argument("--asset", required=True, help="symbol, e.g. ^NDX, ^GSPC")
    p.add_argument("--start", type=_parse_date, default=datetime(2005, 1, 1))
    p.add_argument("--end", type=_parse_date, default=None)
    p.add_argument(
        "--strict",
        action="store_true",
        help="use strict thresholds only (default: liberal enabled)",
    )
    p.add_argument("--output-dir", type=Path, default=Path("backtest"))
    args = p.parse_args(argv)

    src = YFinanceSource()
    daily = src.fetch(args.asset, "1d", start=args.start, end=args.end)
    if daily.empty or len(daily) < 250:
        print(f"error: insufficient daily history for {args.asset}", file=sys.stderr)
        return 2

    payload = build_timeline(args.asset, daily, liberal=not args.strict)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    safe = args.asset.lstrip("^").lower()
    out_path = args.output_dir / f"{safe}.timeline.json"
    out_path.write_text(json.dumps(_json_safe(payload), indent=2, allow_nan=False))

    stats = payload["summary"]
    print(f"{args.asset}: {stats['total']} triggered signals over {payload['n_bars']} bars")
    print(f"  per stufe: {stats['per_stufe']}")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
