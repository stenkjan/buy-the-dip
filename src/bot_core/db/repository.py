from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from bot_core.types import Signal

from .models import AuditLog, Bot, OrderRecord, ParameterRun, Position, SignalRecord


def create_bot(
    session: Session,
    *,
    name: str,
    strategy_name: str,
    asset_symbol: str,
    mode: str = "paper",
    enabled: bool = False,
    broker_name: str = "alpaca",
    config_json: dict[str, Any] | None = None,
) -> Bot:
    bot = Bot(
        name=name,
        strategy_name=strategy_name,
        asset_symbol=asset_symbol,
        mode=mode,
        enabled=enabled,
        broker_name=broker_name,
        config_json=config_json or {},
    )
    session.add(bot)
    session.commit()
    session.refresh(bot)
    return bot


def list_bots(session: Session, *, enabled_only: bool = False) -> list[Bot]:
    stmt = select(Bot)
    if enabled_only:
        stmt = stmt.where(Bot.enabled.is_(True))  # type: ignore[attr-defined]
    return list(session.exec(stmt).all())


def get_bot(session: Session, bot_id: str) -> Bot | None:
    return session.get(Bot, bot_id)


def get_or_create_bot(
    session: Session,
    *,
    name: str,
    strategy_name: str,
    asset_symbol: str,
    **kwargs: Any,
) -> Bot:
    """Idempotent bot lookup by (strategy_name, asset_symbol).

    Used by the persistence path so repeated snapshot runs attach signals to a
    single stable bot per asset rather than creating a new one each run.
    """
    stmt = select(Bot).where(
        Bot.strategy_name == strategy_name,
        Bot.asset_symbol == asset_symbol,
    )
    existing = session.exec(stmt).first()
    if existing is not None:
        return existing
    return create_bot(
        session,
        name=name,
        strategy_name=strategy_name,
        asset_symbol=asset_symbol,
        **kwargs,
    )


def delete_bot(session: Session, bot_id: str) -> bool:
    bot = session.get(Bot, bot_id)
    if bot is None:
        return False
    session.delete(bot)
    session.commit()
    return True


def list_recent_signals(
    session: Session, bot_id: str, *, limit: int = 100
) -> list[SignalRecord]:
    stmt = (
        select(SignalRecord)
        .where(SignalRecord.bot_id == bot_id)
        .order_by(SignalRecord.timestamp.desc())  # type: ignore[attr-defined]
        .limit(limit)
    )
    return list(session.exec(stmt).all())


def list_positions(session: Session, bot_id: str) -> list[Position]:
    stmt = select(Position).where(Position.bot_id == bot_id)
    return list(session.exec(stmt).all())


def update_bot_config(session: Session, bot_id: str, *, config_json: dict[str, Any]) -> Bot:
    bot = session.get(Bot, bot_id)
    if bot is None:
        raise ValueError(f"bot {bot_id} not found")
    bot.config_json = config_json
    bot.updated_at = datetime.now(UTC)
    session.add(bot)
    session.commit()
    session.refresh(bot)
    return bot


def update_bot(
    session: Session,
    bot_id: str,
    *,
    name: str | None = None,
    mode: str | None = None,
    enabled: bool | None = None,
    config_json: dict[str, Any] | None = None,
) -> Bot:
    """Partial update of a bot. Only non-None fields are applied."""
    bot = session.get(Bot, bot_id)
    if bot is None:
        raise ValueError(f"bot {bot_id} not found")
    if name is not None:
        bot.name = name
    if mode is not None:
        bot.mode = mode
    if enabled is not None:
        bot.enabled = enabled
    if config_json is not None:
        bot.config_json = config_json
    bot.updated_at = datetime.now(UTC)
    session.add(bot)
    session.commit()
    session.refresh(bot)
    return bot


def set_bot_enabled(session: Session, bot_id: str, enabled: bool) -> Bot:
    bot = session.get(Bot, bot_id)
    if bot is None:
        raise ValueError(f"bot {bot_id} not found")
    bot.enabled = enabled
    bot.updated_at = datetime.now(UTC)
    session.add(bot)
    session.commit()
    session.refresh(bot)
    return bot


def record_signal(session: Session, bot_id: str, signal: Signal) -> SignalRecord:
    record = SignalRecord(
        bot_id=bot_id,
        timestamp=signal.timestamp,
        stufe=signal.stufe,
        rsi_value=signal.rsi_value,
        rsi_threshold=signal.rsi_threshold,
        price=signal.price,
        triggered=signal.triggered,
        payload_json=signal.to_dict(),
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def record_order(
    session: Session,
    bot_id: str,
    signal_id: str | None,
    broker_response: dict[str, Any],
) -> OrderRecord:
    record = OrderRecord(
        bot_id=bot_id,
        signal_id=signal_id,
        broker_order_id=str(broker_response["id"]),
        side=broker_response["side"],
        qty=float(broker_response["qty"]),
        limit_price=broker_response.get("limit_price"),
        status=broker_response.get("status", "pending"),
        raw_response_json=broker_response,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def update_order_status(
    session: Session,
    broker_order_id: str,
    *,
    status: str,
    filled_at: datetime | None = None,
    fill_price: float | None = None,
    fill_qty: float | None = None,
) -> OrderRecord:
    stmt = select(OrderRecord).where(OrderRecord.broker_order_id == broker_order_id)
    record = session.exec(stmt).one()
    record.status = status
    if filled_at is not None:
        record.filled_at = filled_at
    if fill_price is not None:
        record.fill_price = fill_price
    if fill_qty is not None:
        record.fill_qty = fill_qty
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def upsert_position(
    session: Session,
    bot_id: str,
    symbol: str,
    qty: float,
    avg_entry_price: float,
    market_value: float,
    unrealized_pl: float,
) -> Position:
    stmt = select(Position).where(Position.bot_id == bot_id, Position.symbol == symbol)
    pos = session.exec(stmt).one_or_none()
    if pos is None:
        pos = Position(bot_id=bot_id, symbol=symbol)
    pos.qty = qty
    pos.avg_entry_price = avg_entry_price
    pos.market_value = market_value
    pos.unrealized_pl = unrealized_pl
    pos.updated_at = datetime.now(UTC)
    session.add(pos)
    session.commit()
    session.refresh(pos)
    return pos


def audit(
    session: Session,
    event_type: str,
    message: str,
    *,
    bot_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        bot_id=bot_id,
        event_type=event_type,
        message=message,
        context_json=context or {},
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def record_parameter_run(
    session: Session,
    strategy_name: str,
    params: dict[str, Any],
    results: dict[str, Any],
    *,
    bot_id: str | None = None,
) -> ParameterRun:
    run = ParameterRun(
        bot_id=bot_id,
        strategy_name=strategy_name,
        params_json=params,
        backtest_window_start=results.get("window_start"),
        backtest_window_end=results.get("window_end"),
        total_signals=int(results.get("total_signals", 0)),
        win_rate=results.get("win_rate"),
        mean_forward_return=results.get("mean_forward_return"),
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run
