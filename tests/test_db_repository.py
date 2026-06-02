from __future__ import annotations

from datetime import UTC, datetime

from bot_core.db import repository as repo
from bot_core.types import Signal


def _make_bot(session):
    return repo.create_bot(
        session,
        name="ndx",
        strategy_name="buy_the_dip",
        asset_symbol="^NDX",
        config_json={"v": 1},
    )


def test_create_and_list_bots(db_session):
    a = _make_bot(db_session)
    b = repo.create_bot(
        db_session, name="spx", strategy_name="buy_the_dip", asset_symbol="^GSPC", enabled=True
    )
    all_bots = repo.list_bots(db_session)
    assert {bot.id for bot in all_bots} == {a.id, b.id}
    enabled = repo.list_bots(db_session, enabled_only=True)
    assert [bot.id for bot in enabled] == [b.id]


def test_set_bot_enabled_and_update_config(db_session):
    bot = _make_bot(db_session)
    repo.set_bot_enabled(db_session, bot.id, True)
    assert repo.get_bot(db_session, bot.id).enabled is True

    repo.update_bot_config(db_session, bot.id, config_json={"k": "v"})
    assert repo.get_bot(db_session, bot.id).config_json == {"k": "v"}


def test_record_signal_and_order_and_audit(db_session):
    bot = _make_bot(db_session)
    sig = Signal(
        symbol="^NDX",
        timestamp=datetime(2025, 5, 1, tzinfo=UTC),
        triggered=True,
        stufe=1,
        rsi_value=28.0,
        rsi_threshold=30.0,
        price=15000.0,
    )
    sig_rec = repo.record_signal(db_session, bot.id, sig)
    assert sig_rec.triggered is True
    assert sig_rec.payload_json["symbol"] == "^NDX"

    order_rec = repo.record_order(
        db_session,
        bot.id,
        sig_rec.id,
        broker_response={
            "id": "alpaca-1",
            "side": "buy",
            "qty": 1.5,
            "status": "accepted",
            "limit_price": 14990.0,
        },
    )
    assert order_rec.broker_order_id == "alpaca-1"
    assert order_rec.status == "accepted"

    updated = repo.update_order_status(
        db_session,
        "alpaca-1",
        status="filled",
        filled_at=datetime(2025, 5, 1, 14, 30, tzinfo=UTC),
        fill_price=14990.0,
        fill_qty=1.5,
    )
    assert updated.status == "filled"
    assert updated.fill_price == 14990.0

    entry = repo.audit(
        db_session, "order_submitted", "buy 1.5 ^NDX", bot_id=bot.id, context={"qty": 1.5}
    )
    assert entry.event_type == "order_submitted"
    assert entry.context_json == {"qty": 1.5}


def test_upsert_position_inserts_then_updates(db_session):
    bot = _make_bot(db_session)
    p1 = repo.upsert_position(db_session, bot.id, "^NDX", 1.0, 100.0, 100.0, 0.0)
    p2 = repo.upsert_position(db_session, bot.id, "^NDX", 1.5, 110.0, 165.0, 5.0)
    assert p1.id == p2.id  # same row, updated in place
    assert p2.qty == 1.5
    assert p2.avg_entry_price == 110.0


def test_record_parameter_run(db_session):
    run = repo.record_parameter_run(
        db_session,
        "buy_the_dip",
        params={"rsi_threshold_stufe1": 30},
        results={"total_signals": 12, "win_rate": 0.66, "mean_forward_return": 0.04},
    )
    assert run.total_signals == 12
    assert run.win_rate == 0.66
