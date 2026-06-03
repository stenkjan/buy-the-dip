"""Paper-trade enabled bots against the current signal.

For each enabled bot in the database: build the bot's strategy from its
``config_json``, evaluate the live signal, persist a SignalRecord, and — when
the signal triggered — run the risk-guarded executor to place a paper order.

Opt-in and paper-only. Live mode is refused by the executor. Requires a
database (POSTGRES_URL or local SQLite) and, unless ``--dry-run``, Alpaca paper
credentials (APCA_API_KEY_ID / APCA_API_SECRET_KEY).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from typing import Any

from bot_core.brokers.base import Broker, BrokerError
from bot_core.db import repository as repo
from bot_core.db.models import Bot
from bot_core.execution import RiskGuards, TradeDecision, execute_signal
from bot_core.types import Signal
from strategies.buy_the_dip import BuyTheDipConfig, get_strategy

from ._common import snapshot_asset


def strategy_config_from_bot(bot: Bot) -> BuyTheDipConfig:
    """Build the strategy config from a bot's config_json, falling back to
    BuyTheDipConfig defaults for any unset field."""
    c = bot.config_json or {}
    d = BuyTheDipConfig()
    return BuyTheDipConfig(
        rsi_threshold_stufe1=float(c.get("rsi_threshold_stufe1", d.rsi_threshold_stufe1)),
        rsi_threshold_stufe2=float(c.get("rsi_threshold_stufe2", d.rsi_threshold_stufe2)),
        rsi_threshold_stufe3=float(c.get("rsi_threshold_stufe3", d.rsi_threshold_stufe3)),
        rsi_threshold_stufe1_liberal=float(
            c.get("rsi_threshold_stufe1_liberal", d.rsi_threshold_stufe1_liberal)
        ),
        rsi_threshold_stufe2_liberal=float(
            c.get("rsi_threshold_stufe2_liberal", d.rsi_threshold_stufe2_liberal)
        ),
        rsi_threshold_stufe3_liberal=float(
            c.get("rsi_threshold_stufe3_liberal", d.rsi_threshold_stufe3_liberal)
        ),
        liberal=bool(c.get("liberal", d.liberal)),
        macro_reclaim_window_weeks=int(
            c.get("macro_reclaim_window_weeks", d.macro_reclaim_window_weeks)
        ),
    )


def evaluate_bot_signal(bot: Bot) -> Signal | None:
    """Live signal for one bot using its own thresholds. None if no data."""
    data = snapshot_asset(bot.asset_symbol)
    if data is None:
        return None
    return get_strategy(strategy_config_from_bot(bot)).evaluate(data)


def run(
    session: Any,
    bots: list[Bot],
    broker_factory: Callable[[str], Broker],
    *,
    dry_run: bool = False,
) -> list[TradeDecision]:
    decisions: list[TradeDecision] = []
    for bot in bots:
        signal = evaluate_bot_signal(bot)
        if signal is None:
            decisions.append(
                TradeDecision(bot.id, bot.asset_symbol, "skipped", "no market data")
            )
            continue
        record = repo.record_signal(session, bot.id, signal)
        if not signal.triggered:
            decisions.append(
                TradeDecision(bot.id, bot.asset_symbol, "skipped", "signal not triggered")
            )
            continue
        try:
            broker = broker_factory(bot.mode)
        except BrokerError as exc:
            decisions.append(
                TradeDecision(bot.id, bot.asset_symbol, "skipped", f"broker unavailable: {exc}")
            )
            continue
        cfg = bot.config_json or {}
        decisions.append(
            execute_signal(
                session,
                bot,
                signal,
                broker,
                guards=RiskGuards.from_dict(cfg.get("guards")),
                asset_allocation_pct=float(cfg.get("asset_allocation_pct", 0.25)),
                aggressiveness=float(cfg.get("aggressiveness", 0.5)),
                signal_id=record.id,
                dry_run=dry_run,
            )
        )
    return decisions


def _default_broker_factory(mode: str) -> Broker:
    from bot_core.brokers.alpaca import AlpacaBroker

    return AlpacaBroker(mode=mode)  # type: ignore[arg-type]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="btd-trade",
        description="Paper-trade enabled bots against the current signal",
    )
    p.add_argument("--bot", default=None, help="only trade this bot id (default: all enabled)")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="evaluate + size + run guards but do not place orders",
    )
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
            bots = [bot] if bot.enabled else []
        else:
            bots = repo.list_bots(session, enabled_only=True)

        if not bots:
            print("no enabled bots to trade")
            return 0

        decisions = run(session, bots, _default_broker_factory, dry_run=args.dry_run)

    placed = sum(1 for d in decisions if d.action == "placed")
    for d in decisions:
        extra = f" [{', '.join(d.violations)}]" if d.violations else ""
        suffix = f" order={d.order_id}" if d.order_id else ""
        print(f"{d.symbol}: {d.action} — {d.reason}{suffix}{extra}")
    print(f"{'(dry run) ' if args.dry_run else ''}placed {placed} order(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
