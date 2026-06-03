from __future__ import annotations

from bot_core.brokers.base import BrokerOrder, BrokerPosition
from bot_core.db import repository as repo
from bot_core.execution import refresh_orders


class FakeBroker:
    name = "fake"
    mode = "paper"

    def __init__(self, order: BrokerOrder, positions: list[BrokerPosition]):
        self._order = order
        self._positions = positions

    def get_order(self, order_id):
        return self._order

    def get_positions(self):
        return self._positions

    def get_account(self):  # pragma: no cover
        raise NotImplementedError

    def place_market_order(self, *a, **k):  # pragma: no cover
        raise NotImplementedError

    def place_limit_order(self, *a, **k):  # pragma: no cover
        raise NotImplementedError

    def cancel_order(self, order_id):  # pragma: no cover
        raise NotImplementedError


def _bot(db_session):
    return repo.create_bot(
        db_session, name="ndx", strategy_name="buy_the_dip", asset_symbol="^NDX",
        mode="paper", enabled=True,
    )


def _open_order(db_session, bot_id):
    return repo.record_order(
        db_session, bot_id, None,
        {"id": "ord-1", "side": "buy", "qty": 10.0, "status": "accepted"},
    )


def test_refresh_marks_filled_and_syncs_position(db_session):
    bot = _bot(db_session)
    _open_order(db_session, bot.id)
    assert len(repo.list_open_orders(db_session, bot.id)) == 1

    filled = BrokerOrder(
        id="ord-1", symbol="QQQ", side="buy", qty=10.0, status="filled",
        limit_price=None, filled_qty=10.0, filled_avg_price=99.5, submitted_at=None,
    )
    pos = BrokerPosition(
        symbol="QQQ", qty=10.0, avg_entry_price=99.5, market_value=1000.0, unrealized_pl=5.0
    )
    res = refresh_orders(db_session, bot, FakeBroker(filled, [pos]))

    assert res.open_orders == 1 and res.updated == 1 and res.filled == 1
    assert res.positions_synced == 1
    # order is no longer open and is recorded as filled with fill data
    assert repo.list_open_orders(db_session, bot.id) == []
    orders = repo.list_orders(db_session, bot.id)
    assert orders[0].status == "filled" and orders[0].fill_price == 99.5
    positions = repo.list_positions(db_session, bot.id)
    assert len(positions) == 1 and positions[0].qty == 10.0


def test_refresh_keeps_open_order_open(db_session):
    bot = _bot(db_session)
    _open_order(db_session, bot.id)
    still = BrokerOrder(
        id="ord-1", symbol="QQQ", side="buy", qty=10.0, status="accepted",
        limit_price=None, filled_qty=0.0, filled_avg_price=None, submitted_at=None,
    )
    res = refresh_orders(db_session, bot, FakeBroker(still, []))
    assert res.filled == 0
    assert len(repo.list_open_orders(db_session, bot.id)) == 1
