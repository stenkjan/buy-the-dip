from __future__ import annotations

import argparse
import csv
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from bot_core.data import YFinanceSource
from bot_core.indicators import ema, resample_ohlc, rsi_wilder

DEFAULT_FIXTURE = Path("fixtures/tradingview.csv")
DEFAULT_RSI_TOL = 0.5         # absolute RSI points
DEFAULT_EMA_TOL_PCT = 1.0     # % of EMA value

# Tolerance for date matching: yfinance's daily bar timestamps may be a few
# hours off from the user's calendar date. We accept the closest bar within
# this many trading sessions of the requested date.
DATE_MATCH_DAYS = 3


def _nearest_bar(df: pd.DataFrame, target: datetime) -> pd.Timestamp | None:
    target_ts = pd.Timestamp(target, tz="UTC")
    diffs = (df.index - target_ts).total_seconds().abs()
    idx = int(diffs.argmin())
    if diffs[idx] > DATE_MATCH_DAYS * 86400:
        return None
    return df.index[idx]


def _compute_expected(symbol: str, when: datetime) -> dict[str, float] | None:
    src = YFinanceSource()
    end = when + timedelta(days=5)
    start = datetime(min(when.year - 6, 2000), 1, 1, tzinfo=UTC)
    daily = src.fetch(symbol, "1d", start=start, end=end)
    if daily.empty or len(daily) < 250:
        return None
    bar_ts = _nearest_bar(daily, when)
    if bar_ts is None:
        return None
    weekly = resample_ohlc(daily, "1W")

    ema_d_series = ema(daily["close"], 200)
    ema_w_series = ema(weekly["close"], 200).reindex(daily.index, method="ffill")
    rsi_1d_series = rsi_wilder(daily["close"], 14)
    rsi_1w_series = rsi_wilder(weekly["close"], 14).reindex(daily.index, method="ffill")

    return {
        "close": float(daily.loc[bar_ts, "close"]),
        "ema200_daily": float(ema_d_series.loc[bar_ts]),
        "ema200_weekly": float(ema_w_series.loc[bar_ts]),
        "rsi_1d": float(rsi_1d_series.loc[bar_ts]),
        "rsi_1w": float(rsi_1w_series.loc[bar_ts]),
        "matched_bar": str(bar_ts.date()),
    }


def _compare(expected: dict[str, float], row: dict[str, str], rsi_tol: float, ema_tol_pct: float):
    out = []
    for field, tol_kind in (
        ("close", ("pct", ema_tol_pct)),
        ("ema200_daily", ("pct", ema_tol_pct)),
        ("ema200_weekly", ("pct", ema_tol_pct)),
        ("rsi_1d", ("abs", rsi_tol)),
        ("rsi_1w", ("abs", rsi_tol)),
    ):
        cell = (row.get(field) or "").strip()
        if not cell:
            out.append((field, expected[field], None, "skip"))
            continue
        tv = float(cell)
        kind, tol = tol_kind
        if kind == "abs":
            ok = abs(expected[field] - tv) <= tol
        else:
            ok = abs(expected[field] - tv) <= abs(tv) * tol / 100.0
        out.append((field, expected[field], tv, "ok" if ok else "MISMATCH"))
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="btd-validate-tv")
    p.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    p.add_argument("--rsi-tol", type=float, default=DEFAULT_RSI_TOL)
    p.add_argument("--ema-tol-pct", type=float, default=DEFAULT_EMA_TOL_PCT)
    args = p.parse_args(argv)

    if not args.fixture.exists():
        print(f"error: fixture not found: {args.fixture}", file=sys.stderr)
        return 2

    rows = list(csv.DictReader(args.fixture.open()))
    if not rows:
        print(f"warning: {args.fixture} is empty", file=sys.stderr)
        return 0

    mismatches = 0
    checked = 0
    skipped = 0
    for row in rows:
        symbol = row["symbol"]
        when = datetime.fromisoformat(row["date"]).replace(tzinfo=UTC)
        expected = _compute_expected(symbol, when)
        if expected is None:
            print(f"{symbol} {row['date']}: no data — skipping")
            skipped += 1
            continue
        print(f"{symbol} {row['date']} (bar {expected['matched_bar']}):")
        results = _compare(expected, row, args.rsi_tol, args.ema_tol_pct)
        for field, computed, tv, status in results:
            if status == "skip":
                continue
            checked += 1
            marker = "  ok" if status == "ok" else "  ❌ MISMATCH"
            print(f"  {field:14s} computed={computed:>10.3f} tv={tv:>10.3f}  {marker}")
            if status == "MISMATCH":
                mismatches += 1

    print(f"\nchecked {checked} cells, {mismatches} mismatches, {skipped} rows skipped")
    return 0 if mismatches == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
