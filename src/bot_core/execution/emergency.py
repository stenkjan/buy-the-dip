"""Emergency stop / kill switch.

Pauses every bot and best-effort cancels their open orders. Pausing happens in
the database regardless of broker availability — the whole point of a kill
switch is that it works even when the broker is unreachable; order
cancellation is attempted on top and any failure is reported, not fatal.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from sqlmodel import Session

from bot_core.brokers.base import Broker, BrokerError
from bot_core.db import repository as repo
from bot_core.db.models import Bot


@dataclass
class StopResult:
    bots_paused: int = 0
    orders_cancelled: int = 0
    errors: list[str] = field(default_factory=list)


def emergency_stop(
    session: Session,
    bots: list[Bot],
    broker_factory: Callable[[str], Broker],
) -> StopResult:
    result = StopResult()
    for bot in bots:
        open_orders = repo.list_open_orders(session, bot.id)
        broker: Broker | None = None
        if open_orders:
            try:
                broker = broker_factory(bot.mode)
            except BrokerError as exc:
                result.errors.append(f"{bot.name}: broker unavailable, orders not cancelled: {exc}")
        for order in open_orders:
            if broker is not None:
                try:
                    broker.cancel_order(order.broker_order_id)
                except BrokerError as exc:
                    result.errors.append(
                        f"{bot.name}: cancel {order.broker_order_id} failed: {exc}"
                    )
                    continue
            repo.update_order_status(session, order.broker_order_id, status="cancelled")
            result.orders_cancelled += 1

        if bot.enabled:
            repo.set_bot_enabled(session, bot.id, False)
            result.bots_paused += 1
        repo.audit(
            session, "kill_switch", f"emergency stop: {bot.name} paused",
            bot_id=bot.id,
            context={"open_orders": len(open_orders)},
        )
    return result
