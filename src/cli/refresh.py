"""Refresh open paper-order statuses and sync positions for enabled bots.

Polls the broker for each bot's open orders, updates OrderRecord rows + audits
fills, and syncs the bot's position. Requires a database and Alpaca
credentials. Safe to run on a schedule.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from typing import Any

from bot_core.brokers.base import Broker, BrokerError
from bot_core.db import repository as repo
from bot_core.db.models import Bot
from bot_core.execution import RefreshResult, refresh_orders


def run(
    session: Any, bots: list[Bot], broker_factory: Callable[[str], Broker]
) -> list[RefreshResult]:
    results: list[RefreshResult] = []
    for bot in bots:
        try:
            broker = broker_factory(bot.mode)
        except BrokerError as exc:
            results.append(RefreshResult(bot_id=bot.id, error=f"broker unavailable: {exc}"))
            continue
        results.append(refresh_orders(session, bot, broker))
    return results


def _default_broker_factory(mode: str) -> Broker:
    from bot_core.brokers.alpaca import AlpacaBroker

    return AlpacaBroker(mode=mode)  # type: ignore[arg-type]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="btd-refresh",
        description="Refresh open order statuses and positions for enabled bots",
    )
    p.add_argument("--bot", default=None, help="only refresh this bot id (default: all enabled)")
    args = p.parse_args(argv)

    from sqlmodel import Session, SQLModel

    from bot_core.db import models  # noqa: F401 — registers tables
    from bot_core.db.session import get_engine

    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        if args.bot:
            bot = repo.get_bot(session, args.bot)
            if bot is None:
                print(f"error: bot {args.bot} not found", file=sys.stderr)
                return 2
            bots = [bot]
        else:
            bots = repo.list_bots(session, enabled_only=True)

        if not bots:
            print("no bots to refresh")
            return 0

        results = run(session, bots, _default_broker_factory)

    for r in results:
        if r.error:
            print(f"{r.bot_id}: {r.error}")
        else:
            print(
                f"{r.bot_id}: {r.open_orders} open, {r.updated} updated, "
                f"{r.filled} filled, {r.positions_synced} position(s) synced"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
