from __future__ import annotations

from sqlmodel import select

from bot_core.brokers.base import BrokerError
from bot_core.db import repository as repo
from bot_core.db.models import AuditLog
from bot_core.execution import emergency_stop


class FakeBroker:
    name = "fake"
    mode = "paper"

    def __init__(self, *, fail_cancel: bool = False):
        self.fail_cancel = fail_cancel
        self.cancelled: list[str] = []

    def cancel_order(self, order_id):
        if self.fail_cancel:
            raise BrokerError("cancel boom")
        self.cancelled.append(order_id)

    def get_account(self):  # pragma: no cover
        raise NotImplementedError

    def get_positions(self):  # pragma: no cover
        raise NotImplementedError

    def get_order(self, order_id):  # pragma: no cover
        raise NotImplementedError

    def place_market_order(self, *a, **k):  # pragma: no cover
        raise NotImplementedError

    def place_limit_order(self, *a, **k):  # pragma: no cover
        raise NotImplementedError


def _bot(db_session, name, *, enabled=True):
    return repo.create_bot(
        db_session, name=name, strategy_name="buy_the_dip", asset_symbol="^NDX",
        mode="paper", enabled=enabled,
    )


def test_emergency_stop_pauses_and_cancels(db_session):
    a = _bot(db_session, "a")
    b = _bot(db_session, "b")
    repo.record_order(
        db_session, a.id, None,
        {"id": "o1", "side": "buy", "qty": 1.0, "status": "accepted"},
    )
    broker = FakeBroker()
    res = emergency_stop(db_session, [a, b], lambda mode: broker)

    assert res.bots_paused == 2
    assert res.orders_cancelled == 1
    assert res.errors == []
    assert broker.cancelled == ["o1"]
    assert repo.get_bot(db_session, a.id).enabled is False
    assert repo.get_bot(db_session, b.id).enabled is False
    assert repo.list_open_orders(db_session, a.id) == []
    kills = db_session.exec(select(AuditLog).where(AuditLog.event_type == "kill_switch")).all()
    assert len(kills) == 2


def test_emergency_stop_pauses_even_if_cancel_fails(db_session):
    a = _bot(db_session, "a")
    repo.record_order(
        db_session, a.id, None,
        {"id": "o1", "side": "buy", "qty": 1.0, "status": "accepted"},
    )
    res = emergency_stop(db_session, [a], lambda mode: FakeBroker(fail_cancel=True))
    # pausing still happens; the order stays open and the failure is reported
    assert res.bots_paused == 1
    assert res.orders_cancelled == 0
    assert res.errors and "cancel" in res.errors[0]
    assert repo.get_bot(db_session, a.id).enabled is False
    assert len(repo.list_open_orders(db_session, a.id)) == 1
