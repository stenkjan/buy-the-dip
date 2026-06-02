from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import select

from bot_core.db.models import (
    AuditLog,
    Bot,
    OrderRecord,
    ParameterRun,
    Position,
    SignalRecord,
)


def test_bot_roundtrip_with_json_config(db_session):
    bot = Bot(
        name="ndx-paper",
        strategy_name="buy_the_dip",
        asset_symbol="^NDX",
        config_json={"rsi_threshold_stufe1": 35, "nested": {"k": [1, 2]}},
    )
    db_session.add(bot)
    db_session.commit()

    fetched = db_session.exec(select(Bot)).one()
    assert fetched.id == bot.id
    assert fetched.config_json == {"rsi_threshold_stufe1": 35, "nested": {"k": [1, 2]}}
    assert isinstance(fetched.created_at, datetime)


def test_signal_record_indexed_by_bot_ts(db_session):
    bot = Bot(name="b", strategy_name="buy_the_dip", asset_symbol="^GSPC")
    db_session.add(bot)
    db_session.commit()
    db_session.refresh(bot)
    sig = SignalRecord(
        bot_id=bot.id,
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        stufe=1,
        rsi_value=29.0,
        rsi_threshold=30.0,
        price=15000.0,
        triggered=True,
        payload_json={"extras": {"macro_reclaim": False}},
    )
    db_session.add(sig)
    db_session.commit()
    got = db_session.exec(select(SignalRecord)).one()
    assert got.triggered is True
    assert got.payload_json["extras"]["macro_reclaim"] is False


def test_order_record_with_optional_fields(db_session):
    bot = Bot(name="b", strategy_name="buy_the_dip", asset_symbol="QQQ")
    db_session.add(bot)
    db_session.commit()
    db_session.refresh(bot)
    o = OrderRecord(
        bot_id=bot.id,
        signal_id=None,
        broker_order_id="brk-1",
        side="buy",
        qty=1.0,
        raw_response_json={"venue": "alpaca"},
    )
    db_session.add(o)
    db_session.commit()
    got = db_session.exec(select(OrderRecord)).one()
    assert got.status == "pending"
    assert got.fill_price is None


def test_position_and_audit_and_parameter_run(db_session):
    bot = Bot(name="b", strategy_name="buy_the_dip", asset_symbol="SPY")
    db_session.add(bot)
    db_session.commit()
    db_session.refresh(bot)

    pos = Position(bot_id=bot.id, symbol="SPY", qty=2.5, avg_entry_price=400.0)
    audit = AuditLog(bot_id=bot.id, event_type="signal_evaluated", message="ok")
    run = ParameterRun(strategy_name="buy_the_dip", params_json={"foo": 1}, total_signals=42)
    db_session.add_all([pos, audit, run])
    db_session.commit()

    assert db_session.exec(select(Position)).one().qty == 2.5
    assert db_session.exec(select(AuditLog)).one().event_type == "signal_evaluated"
    assert db_session.exec(select(ParameterRun)).one().total_signals == 42
