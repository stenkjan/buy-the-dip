"""Order-status refresh + position sync.

Polls the broker for the current state of a bot's open orders, updates the
persisted OrderRecord rows, audits fills, and syncs the bot's position for its
tradable symbol from the broker. Pure orchestration over the repository +
broker; the broker is injected so this is testable with a fake.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlmodel import Session

from bot_core.brokers.base import Broker, BrokerError
from bot_core.data import to_alpaca_symbol
from bot_core.db import repository as repo
from bot_core.db.models import Bot

_FILLED = "filled"


@dataclass
class RefreshResult:
    bot_id: str
    open_orders: int = 0
    updated: int = 0
    filled: int = 0
    positions_synced: int = 0
    error: str | None = None


def refresh_orders(
    session: Session, bot: Bot, broker: Broker, *, now: datetime | None = None
) -> RefreshResult:
    now = now or datetime.now(UTC)
    result = RefreshResult(bot_id=bot.id)

    open_orders = repo.list_open_orders(session, bot.id)
    result.open_orders = len(open_orders)
    for rec in open_orders:
        try:
            order = broker.get_order(rec.broker_order_id)
        except BrokerError:
            continue
        repo.update_order_status(
            session,
            rec.broker_order_id,
            status=order.status,
            filled_at=now if order.status == _FILLED else None,
            fill_price=order.filled_avg_price,
            fill_qty=order.filled_qty or None,
        )
        result.updated += 1
        if order.status == _FILLED:
            result.filled += 1
            repo.audit(
                session, "order_filled",
                f"{bot.name}: order {rec.broker_order_id} filled",
                bot_id=bot.id,
                context={
                    "symbol": order.symbol,
                    "filled_qty": order.filled_qty,
                    "filled_avg_price": order.filled_avg_price,
                },
            )

    # Sync the bot's position for its tradable symbol from the broker (the
    # authoritative source) rather than recomputing from fills.
    target = to_alpaca_symbol(bot.asset_symbol)
    try:
        positions = broker.get_positions()
    except BrokerError as exc:
        result.error = f"position sync skipped: {exc}"
        return result
    for p in positions:
        if p.symbol == target:
            repo.upsert_position(
                session, bot.id, p.symbol, p.qty, p.avg_entry_price,
                p.market_value, p.unrealized_pl,
            )
            result.positions_synced += 1
    return result
