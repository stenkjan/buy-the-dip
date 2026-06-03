from __future__ import annotations

from datetime import UTC, datetime

from bot_core.brokers.base import Account, BrokerOrder
from bot_core.db import repository as repo
from bot_core.execution import RiskGuards, execute_signal
from bot_core.types import Signal


class FakeBroker:
    name = "fake"
    mode = "paper"

    def __init__(self, cash: float = 100_000.0, equity: float = 100_000.0):
        self.account = Account(cash=cash, buying_power=cash, equity=equity, currency="USD")
        self.placed: list[BrokerOrder] = []

    def get_account(self) -> Account:
        return self.account

    def get_positions(self):
        return []

    def place_market_order(self, symbol, side, qty):
        o = BrokerOrder(
            id=f"ord-{len(self.placed) + 1}", symbol=symbol, side=side, qty=qty,
            status="accepted", limit_price=None, filled_qty=0.0,
            filled_avg_price=None, submitted_at=None,
        )
        self.placed.append(o)
        return o

    def place_limit_order(self, *a, **k):  # pragma: no cover
        raise NotImplementedError

    def get_order(self, order_id):  # pragma: no cover
        raise NotImplementedError

    def cancel_order(self, order_id):  # pragma: no cover
        raise NotImplementedError


def _signal(triggered=True, price=100.0, stufe=1):
    return Signal(
        symbol="^NDX", timestamp=datetime(2026, 6, 3, tzinfo=UTC), triggered=triggered,
        stufe=stufe, rsi_value=28.0, rsi_threshold=30.0, price=price,
        tranche_pct_range=(10.0, 20.0),
    )


def _bot(db_session, *, mode="paper", enabled=True):
    return repo.create_bot(
        db_session, name="ndx", strategy_name="buy_the_dip", asset_symbol="^NDX",
        mode=mode, enabled=enabled,
    )


def test_places_paper_order_and_persists(db_session):
    bot = _bot(db_session)
    broker = FakeBroker()
    d = execute_signal(db_session, bot, _signal(), broker, asset_allocation_pct=0.25)
    assert d.action == "placed"
    assert len(broker.placed) == 1
    assert broker.placed[0].symbol == "QQQ"  # ^NDX mapped to its tradable proxy
    orders = repo.list_orders(db_session, bot.id)
    assert len(orders) == 1 and orders[0].side == "buy"


def test_not_triggered_skips(db_session):
    bot = _bot(db_session)
    broker = FakeBroker()
    d = execute_signal(db_session, bot, _signal(triggered=False), broker)
    assert d.action == "skipped" and not broker.placed


def test_live_mode_refused(db_session):
    bot = _bot(db_session, mode="live")
    broker = FakeBroker()
    d = execute_signal(db_session, bot, _signal(), broker)
    assert d.action == "skipped" and "live" in d.reason and not broker.placed


def test_dry_run_does_not_place(db_session):
    bot = _bot(db_session)
    broker = FakeBroker()
    d = execute_signal(db_session, bot, _signal(), broker, dry_run=True)
    assert d.action == "skipped" and d.reason == "dry run"
    assert d.qty > 0 and not broker.placed
    assert repo.list_orders(db_session, bot.id) == []


def test_guards_block_and_audit(db_session):
    bot = _bot(db_session)
    broker = FakeBroker()
    # tight position cap forces a violation; nothing should be placed
    d = execute_signal(
        db_session, bot, _signal(), broker,
        guards=RiskGuards(max_position_pct=0.001), asset_allocation_pct=0.25,
    )
    assert d.action == "skipped" and d.violations
    assert not broker.placed
    audits = [a for a in repo.list_recent_signals(db_session, bot.id)]  # noqa: F841
    # an audit row was written for the block
    from sqlmodel import select

    from bot_core.db.models import AuditLog
    rows = db_session.exec(select(AuditLog).where(AuditLog.event_type == "order_blocked")).all()
    assert len(rows) == 1


def test_below_min_order_skips(db_session):
    bot = _bot(db_session)
    broker = FakeBroker(cash=100.0, equity=100.0)  # 100*0.25*0.15 = 3.75 < min order
    d = execute_signal(db_session, bot, _signal(), broker, asset_allocation_pct=0.25)
    assert d.action == "skipped" and "minimum" in d.reason
    assert not broker.placed
