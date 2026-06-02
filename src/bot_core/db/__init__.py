"""Database layer: SQLModel tables + a thin functional repository.

Engine resolution prefers the pooled `POSTGRES_URL` for app traffic and the
direct `POSTGRES_URL_NON_POOLING` for short-lived processes (migrations, CI).
Falls back to a local SQLite file so tests and offline dev work with no
external DB.
"""

from .models import (
    AuditLog,
    Bot,
    OrderRecord,
    ParameterRun,
    Position,
    SignalRecord,
    SQLModel,
)
from .session import get_engine, get_session, resolve_database_url

__all__ = [
    "AuditLog",
    "Bot",
    "OrderRecord",
    "ParameterRun",
    "Position",
    "SQLModel",
    "SignalRecord",
    "get_engine",
    "get_session",
    "resolve_database_url",
]
