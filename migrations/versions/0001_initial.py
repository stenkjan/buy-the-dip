"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-02

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _json_type() -> sa.types.TypeEngine:
    """JSONB on Postgres, plain JSON elsewhere (SQLite)."""
    return postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "bot",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("strategy_name", sa.String(), nullable=False),
        sa.Column("asset_symbol", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False, server_default="paper"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("broker_name", sa.String(), nullable=False, server_default="alpaca"),
        sa.Column("config_json", _json_type(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bot_name", "bot", ["name"])
    op.create_index("ix_bot_asset_symbol", "bot", ["asset_symbol"])

    op.create_table(
        "signal_record",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bot_id", sa.String(), sa.ForeignKey("bot.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stufe", sa.Integer(), nullable=False),
        sa.Column("rsi_value", sa.Float(), nullable=False),
        sa.Column("rsi_threshold", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("triggered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("payload_json", _json_type(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_signal_record_bot_id", "signal_record", ["bot_id"])
    op.create_index("ix_signal_record_bot_ts", "signal_record", ["bot_id", "timestamp"])

    op.create_table(
        "order_record",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bot_id", sa.String(), sa.ForeignKey("bot.id"), nullable=False),
        sa.Column("signal_id", sa.String(), sa.ForeignKey("signal_record.id"), nullable=True),
        sa.Column("broker_order_id", sa.String(), nullable=False),
        sa.Column("side", sa.String(), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("limit_price", sa.Float(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fill_price", sa.Float(), nullable=True),
        sa.Column("fill_qty", sa.Float(), nullable=True),
        sa.Column("raw_response_json", _json_type(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_order_record_bot", "order_record", ["bot_id"])
    op.create_index("ix_order_record_broker_id", "order_record", ["broker_order_id"])

    op.create_table(
        "position",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bot_id", sa.String(), sa.ForeignKey("bot.id"), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_entry_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("market_value", sa.Float(), nullable=False, server_default="0"),
        sa.Column("unrealized_pl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_position_bot_symbol", "position", ["bot_id", "symbol"], unique=True)

    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bot_id", sa.String(), sa.ForeignKey("bot.id"), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context_json", _json_type(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_event_created", "audit_log", ["event_type", "created_at"])

    op.create_table(
        "parameter_run",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bot_id", sa.String(), sa.ForeignKey("bot.id"), nullable=True),
        sa.Column("strategy_name", sa.String(), nullable=False),
        sa.Column("params_json", _json_type(), nullable=False, server_default="{}"),
        sa.Column("backtest_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("backtest_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_signals", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column("mean_forward_return", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_parameter_run_strategy_name", "parameter_run", ["strategy_name"])


def downgrade() -> None:
    op.drop_index("ix_parameter_run_strategy_name", table_name="parameter_run")
    op.drop_table("parameter_run")
    op.drop_index("ix_audit_event_created", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index("ix_position_bot_symbol", table_name="position")
    op.drop_table("position")
    op.drop_index("ix_order_record_broker_id", table_name="order_record")
    op.drop_index("ix_order_record_bot", table_name="order_record")
    op.drop_table("order_record")
    op.drop_index("ix_signal_record_bot_ts", table_name="signal_record")
    op.drop_index("ix_signal_record_bot_id", table_name="signal_record")
    op.drop_table("signal_record")
    op.drop_index("ix_bot_asset_symbol", table_name="bot")
    op.drop_index("ix_bot_name", table_name="bot")
    op.drop_table("bot")
