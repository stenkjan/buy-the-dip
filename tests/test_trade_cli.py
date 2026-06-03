from __future__ import annotations

from datetime import UTC, datetime

from bot_core.brokers.base import Account, BrokerOrder
from bot_core.db import repository as repo
from bot_core.types import AssetData
from cli import trade as trade_cli


class FakeBroker:
    name = "fake"
    mode = "paper"

    def __init__(self):
        self.account = Account(
            cash=100_000.0, buying_power=100_000.0, equity=100_000.0, currency="USD"
        )
        self.placed: list[BrokerOrder] = []

    def get_account(self):
        return self.account

    def get_positions(self):
        return []

    def place_market_order(self, symbol, side, qty):
        o = BrokerOrder(
            id="ord-1", symbol=symbol, side=side, qty=qty, status="accepted",
            limit_price=None, filled_qty=0.0, filled_avg_price=None, submitted_at=None,
        )
        self.placed.append(o)
        return o

    def place_limit_order(self, *a, **k):  # pragma: no cover
        raise NotImplementedError

    def get_order(self, order_id):  # pragma: no cover
        raise NotImplementedError

    def cancel_order(self, order_id):  # pragma: no cover
        raise NotImplementedError


def _triggered_asset(symbol: str) -> AssetData:
    # close above daily EMA200 → Stufe 1; rsi_12h below threshold → triggered
    return AssetData(
        symbol=symbol, timestamp=datetime(2026, 6, 3, tzinfo=UTC), last_close=100.0,
        ema200_daily=90.0, ema200_weekly=80.0, rsi_12h=25.0, rsi_1d=50.0, rsi_1w=50.0,
    )


def test_strategy_config_from_bot_reads_config_json(db_session):
    bot = repo.create_bot(
        db_session, name="x", strategy_name="buy_the_dip", asset_symbol="^NDX",
        config_json={"rsi_threshold_stufe1": 27.5, "liberal": False},
    )
    cfg = trade_cli.strategy_config_from_bot(bot)
    assert cfg.rsi_threshold_stufe1 == 27.5
    assert cfg.liberal is False
    # unset fields fall back to defaults
    assert cfg.rsi_threshold_stufe2 == 30.0


def test_run_places_order_and_records_signal(db_session, monkeypatch):
    monkeypatch.setattr(trade_cli, "snapshot_asset", _triggered_asset)
    bot = repo.create_bot(
        db_session, name="ndx", strategy_name="buy_the_dip", asset_symbol="^NDX",
        mode="paper", enabled=True,
    )
    broker = FakeBroker()
    decisions = trade_cli.run(db_session, [bot], lambda mode: broker, dry_run=False)
    assert len(decisions) == 1 and decisions[0].action == "placed"
    assert len(broker.placed) == 1
    # the evaluated signal was persisted
    assert len(repo.list_recent_signals(db_session, bot.id)) == 1


def test_run_dry_run_records_signal_but_skips_order(db_session, monkeypatch):
    monkeypatch.setattr(trade_cli, "snapshot_asset", _triggered_asset)
    bot = repo.create_bot(
        db_session, name="ndx", strategy_name="buy_the_dip", asset_symbol="^NDX",
        mode="paper", enabled=True,
    )
    broker = FakeBroker()
    decisions = trade_cli.run(db_session, [bot], lambda mode: broker, dry_run=True)
    assert decisions[0].action == "skipped" and decisions[0].reason == "dry run"
    assert not broker.placed
    assert len(repo.list_recent_signals(db_session, bot.id)) == 1


def test_run_skips_when_no_market_data(db_session, monkeypatch):
    monkeypatch.setattr(trade_cli, "snapshot_asset", lambda symbol: None)
    bot = repo.create_bot(
        db_session, name="ndx", strategy_name="buy_the_dip", asset_symbol="^NDX",
        mode="paper", enabled=True,
    )
    decisions = trade_cli.run(db_session, [bot], lambda mode: FakeBroker(), dry_run=False)
    assert decisions[0].action == "skipped" and "no market data" in decisions[0].reason
