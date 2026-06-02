from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column, Index
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Bot(SQLModel, table=True):
    __tablename__ = "bot"

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    name: str = Field(index=True)
    strategy_name: str
    asset_symbol: str = Field(index=True)
    mode: str = Field(default="paper")  # paper | live
    enabled: bool = Field(default=False)
    broker_name: str = Field(default="alpaca")
    config_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class SignalRecord(SQLModel, table=True):
    __tablename__ = "signal_record"
    __table_args__ = (
        Index("ix_signal_record_bot_ts", "bot_id", "timestamp"),
    )

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    bot_id: str = Field(foreign_key="bot.id", index=True)
    timestamp: datetime
    stufe: int
    rsi_value: float
    rsi_threshold: float
    price: float
    triggered: bool = Field(default=False)
    payload_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow)


class OrderRecord(SQLModel, table=True):
    __tablename__ = "order_record"
    __table_args__ = (
        Index("ix_order_record_bot", "bot_id"),
        Index("ix_order_record_broker_id", "broker_order_id"),
    )

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    bot_id: str = Field(foreign_key="bot.id")
    signal_id: str | None = Field(default=None, foreign_key="signal_record.id")
    broker_order_id: str
    side: str  # buy | sell
    qty: float
    limit_price: float | None = Field(default=None)
    status: str = Field(default="pending")  # pending|filled|cancelled|rejected|partial
    submitted_at: datetime = Field(default_factory=_utcnow)
    filled_at: datetime | None = Field(default=None)
    fill_price: float | None = Field(default=None)
    fill_qty: float | None = Field(default=None)
    raw_response_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class Position(SQLModel, table=True):
    __tablename__ = "position"
    __table_args__ = (
        Index("ix_position_bot_symbol", "bot_id", "symbol", unique=True),
    )

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    bot_id: str = Field(foreign_key="bot.id")
    symbol: str
    qty: float = Field(default=0.0)
    avg_entry_price: float = Field(default=0.0)
    market_value: float = Field(default=0.0)
    unrealized_pl: float = Field(default=0.0)
    updated_at: datetime = Field(default_factory=_utcnow)


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_event_created", "event_type", "created_at"),
    )

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    bot_id: str | None = Field(default=None, foreign_key="bot.id")
    # event_type values: signal_evaluated | order_submitted | order_filled
    # | order_rejected | bot_paused | kill_switch | config_changed
    event_type: str
    message: str
    context_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow)


class ParameterRun(SQLModel, table=True):
    __tablename__ = "parameter_run"

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    bot_id: str | None = Field(default=None, foreign_key="bot.id")
    strategy_name: str = Field(index=True)
    params_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    backtest_window_start: datetime | None = Field(default=None)
    backtest_window_end: datetime | None = Field(default=None)
    total_signals: int = Field(default=0)
    win_rate: float | None = Field(default=None)
    mean_forward_return: float | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)


__all__ = [
    "AuditLog",
    "Bot",
    "OrderRecord",
    "ParameterRun",
    "Position",
    "SQLModel",
    "SignalRecord",
]
