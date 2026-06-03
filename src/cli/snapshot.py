from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bot_core.types import Signal
from strategies.buy_the_dip import get_strategy

from ._common import build_history, build_strategy_config, load_config, snapshot_asset

SCHEMA_VERSION = 1
HISTORY_SCHEMA_VERSION = 1


def _json_safe(value: Any) -> Any:
    """Recursively replace non-finite floats (NaN/inf) with None so the payload
    is valid JSON. Browsers' JSON.parse rejects literal NaN, which would break
    the web dashboard's fetch."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _persist_signals(evaluated: list[tuple[str, Signal]], strategy_name: str) -> int:
    """Write a SignalRecord per evaluated asset to the configured database.

    Opt-in (``--persist``): the public scheduled snapshot keeps running without
    a database. Uses ``get_or_create_bot`` so repeated runs attach to one
    stable bot per asset. Imports are local so the JSON path never needs the DB
    stack. Returns the number of records written.
    """
    from sqlmodel import Session, SQLModel

    from bot_core.db import models  # noqa: F401 — registers tables
    from bot_core.db.repository import get_or_create_bot, record_signal
    from bot_core.db.session import get_engine

    engine = get_engine()
    # checkfirst=True: a no-op when Alembic already provisioned the schema.
    SQLModel.metadata.create_all(engine)
    written = 0
    with Session(engine) as session:
        for symbol, sig in evaluated:
            bot = get_or_create_bot(
                session, name=symbol, strategy_name=strategy_name, asset_symbol=symbol
            )
            record_signal(session, bot.id, sig)
            written += 1
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="btd-snapshot",
        description="Compute current indicator/signal snapshot for all configured assets",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--history-output",
        type=Path,
        default=None,
        help="also write per-asset daily history (close/EMA200/RSI) for the dashboard charts",
    )
    parser.add_argument(
        "--history-bars",
        type=int,
        default=500,
        help="number of recent daily bars to include in the history payload",
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="also write a SignalRecord per asset to the database (requires POSTGRES_URL "
        "or falls back to a local SQLite file)",
    )
    args = parser.parse_args(argv)

    cfg = load_config()
    strategy_config = build_strategy_config(cfg)
    strategy = get_strategy(strategy_config)

    signals: list[dict] = []
    evaluated: list[tuple[str, Signal]] = []
    for symbol in cfg["data"]["assets"]:
        data = snapshot_asset(symbol)
        if data is None:
            continue
        sig = strategy.evaluate(data)
        signals.append(sig.to_dict())
        evaluated.append((symbol, sig))

    now = datetime.now(UTC).isoformat()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now,
        "signals": signals,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(_json_safe(payload), indent=2, allow_nan=False))
    print(f"wrote {args.output} ({len(signals)} signals)")

    if args.history_output is not None:
        assets: dict[str, Any] = {}
        for symbol in cfg["data"]["assets"]:
            rows = build_history(symbol, strategy_config, bars=args.history_bars)
            if rows:
                assets[symbol] = rows
        history_payload = {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "generated_at": now,
            "assets": assets,
        }
        args.history_output.parent.mkdir(parents=True, exist_ok=True)
        args.history_output.write_text(
            json.dumps(_json_safe(history_payload), indent=2, allow_nan=False)
        )
        total = sum(len(v) for v in assets.values())
        print(f"wrote {args.history_output} ({len(assets)} assets, {total} bars)")

    if args.persist:
        try:
            written = _persist_signals(evaluated, strategy.name)
            print(f"persisted {written} signal record(s) to the database")
        except Exception as exc:
            # Persistence is best-effort: never fail the JSON snapshot over it.
            print(f"warning: signal persistence failed: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
