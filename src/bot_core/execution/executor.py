"""Signal → order execution.

Ties the pieces together for one bot + one signal: risk guards → sizing →
broker order → DB persistence (OrderRecord + audit). Paper-only: live mode is
refused here until the validation prerequisite in docs/validation.md and
roadmap phase 7 are met. The broker is injected so this is testable with a
fake.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session

from bot_core.brokers.base import Broker, BrokerError, BrokerOrder
from bot_core.data import to_alpaca_symbol
from bot_core.db import repository as repo
from bot_core.db.models import Bot
from bot_core.types import Signal

from .guards import RiskGuards, evaluate_guards
from .sizing import size_order


@dataclass
class TradeDecision:
    bot_id: str
    symbol: str
    action: str          # "placed" | "skipped"
    reason: str
    order_id: str | None = None
    qty: float = 0.0
    notional: float = 0.0
    violations: list[str] = field(default_factory=list)


def _order_to_payload(order: BrokerOrder, *, qty: float) -> dict[str, Any]:
    return {
        "id": order.id,
        "side": order.side,
        "qty": float(order.qty or qty),
        "limit_price": order.limit_price,
        "status": order.status,
        "symbol": order.symbol,
        "filled_qty": order.filled_qty,
        "filled_avg_price": order.filled_avg_price,
    }


def execute_signal(
    session: Session,
    bot: Bot,
    signal: Signal,
    broker: Broker,
    *,
    guards: RiskGuards | None = None,
    asset_allocation_pct: float = 0.25,
    aggressiveness: float = 0.5,
    drawdown_pct: float | None = None,
    signal_id: str | None = None,
    dry_run: bool = False,
    now: datetime | None = None,
) -> TradeDecision:
    """Evaluate and (unless dry_run) place a paper buy for a triggered signal."""
    now = now or datetime.now(UTC)
    guards = guards or RiskGuards()
    sym = bot.asset_symbol

    def skip(reason: str, violations: list[str] | None = None) -> TradeDecision:
        return TradeDecision(
            bot_id=bot.id, symbol=sym, action="skipped", reason=reason,
            violations=violations or [],
        )

    if not signal.triggered:
        return skip("signal not triggered")
    if not bot.enabled:
        return skip("bot disabled")
    if bot.mode != "paper":
        return skip("live trading disabled (paper-only until validation; see roadmap phase 7)")
    if signal.tranche_pct_range is None:
        return skip("no tranche range on signal")

    try:
        account = broker.get_account()
    except BrokerError as exc:
        return skip(f"broker account fetch failed: {exc}")

    # Signal tranches are whole percents; size_order wants fractions.
    lo, hi = signal.tranche_pct_range
    qty, notional = size_order(
        account_cash=account.cash,
        asset_allocation_pct=asset_allocation_pct,
        tranche_pct_range=(lo / 100.0, hi / 100.0),
        last_close=signal.price,
        aggressiveness=aggressiveness,
    )
    if qty <= 0:
        return skip("sized notional below minimum order")

    recent_buys = [
        o.submitted_at for o in repo.list_orders(session, bot.id) if o.side == "buy"
    ]
    violations = evaluate_guards(
        notional=notional,
        account=account,
        recent_buy_times=recent_buys,
        now=now,
        guards=guards,
        drawdown_pct=drawdown_pct,
    )
    if violations:
        repo.audit(
            session, "order_blocked",
            f"{bot.name}: guards blocked buy of {sym}",
            bot_id=bot.id, context={"violations": violations, "notional": notional},
        )
        return skip("risk guards blocked the order", violations)

    if dry_run:
        return TradeDecision(
            bot_id=bot.id, symbol=sym, action="skipped", reason="dry run",
            qty=qty, notional=notional,
        )

    broker_symbol = to_alpaca_symbol(sym)
    try:
        order = broker.place_market_order(broker_symbol, "buy", qty)
    except BrokerError as exc:
        repo.audit(
            session, "order_rejected", f"{bot.name}: order submit failed: {exc}",
            bot_id=bot.id, context={"symbol": broker_symbol, "qty": qty},
        )
        return skip(f"broker rejected order: {exc}")

    record = repo.record_order(session, bot.id, signal_id, _order_to_payload(order, qty=qty))
    repo.audit(
        session, "order_submitted",
        f"{bot.name}: paper buy {qty} {broker_symbol} (~${notional:,.0f})",
        bot_id=bot.id, context={"order_id": order.id, "status": order.status},
    )
    return TradeDecision(
        bot_id=bot.id, symbol=sym, action="placed",
        reason=f"paper buy {broker_symbol}", order_id=record.broker_order_id,
        qty=qty, notional=notional,
    )
