"""Persist parameter-sweep results for the configured assets.

Runs the threshold grid over history for each asset and writes a ParameterRun
row per grid entry, so the learning loop accumulates a record of how
alternative thresholds would have performed. Suggestions only — never mutates a
bot's config. Meant to run on a schedule (parameter-sweep.yml); persistence is
only meaningful against Postgres (local SQLite is ephemeral in CI).
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from typing import Any

from bot_core.backtest import run_sweep
from bot_core.data import YFinanceSource
from bot_core.db import repository as repo

from ._common import load_config


def run(session: Any, assets: list[str], *, start: datetime) -> int:
    """Run + persist a sweep for each asset. Returns the number of rows written."""
    written = 0
    src = YFinanceSource()
    for asset in assets:
        daily = src.fetch(asset, "1d", start=start)
        if daily.empty or len(daily) < 250:
            print(f"warning: insufficient history for {asset}", file=sys.stderr)
            continue
        results = run_sweep(asset, daily)
        window = {
            "window_start": daily.index[0].to_pydatetime(),
            "window_end": daily.index[-1].to_pydatetime(),
        }
        for r in results:
            repo.record_parameter_run(
                session, "buy_the_dip", r["params"],
                {
                    **window,
                    "total_signals": r["total_signals"],
                    "win_rate": r["win_rate"],
                    "mean_forward_return": r["mean_forward_return"],
                },
            )
            written += 1
        best = results[0] if results else None
        if best is not None:
            print(
                f"{asset}: best {best['params']} "
                f"mean={best['mean_forward_return']} ({len(results)} variants)"
            )
    return written


def _parse_date(s: str) -> datetime:
    return datetime.fromisoformat(s)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="btd-sweep",
        description="Run + persist parameter sweeps for the configured assets",
    )
    p.add_argument("--asset", action="append", help="asset (repeatable); default: config assets")
    p.add_argument("--start", type=_parse_date, default=datetime(2005, 1, 1))
    args = p.parse_args(argv)

    assets = args.asset or load_config()["data"]["assets"]

    from sqlmodel import Session, SQLModel

    from bot_core.db import models  # noqa: F401 — registers tables
    from bot_core.db.session import get_engine

    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        written = run(session, list(assets), start=args.start)

    print(f"wrote {written} parameter_run row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
