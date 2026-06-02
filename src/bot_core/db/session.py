from __future__ import annotations

import os
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

DEFAULT_SQLITE_URL = "sqlite:///./buythedip.db"


def resolve_database_url(*, prefer_non_pooling: bool = False) -> str:
    """Pick the right DB URL for this context.

    Short-lived processes (migrations, CI scripts) should set
    `prefer_non_pooling=True` so we hit Vercel Postgres' direct connection
    string instead of the pgBouncer pool, which doesn't tolerate DDL well.
    Falls back to a local SQLite file so tests and offline dev work without
    Postgres available.
    """
    if prefer_non_pooling:
        url = os.getenv("POSTGRES_URL_NON_POOLING") or os.getenv("POSTGRES_URL")
    else:
        url = os.getenv("POSTGRES_URL") or os.getenv("POSTGRES_URL_NON_POOLING")
    return url or DEFAULT_SQLITE_URL


@lru_cache(maxsize=4)
def get_engine(url: str | None = None, *, prefer_non_pooling: bool = False) -> Engine:
    resolved = url or resolve_database_url(prefer_non_pooling=prefer_non_pooling)
    connect_args: dict[str, object] = {}
    if resolved.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(resolved, connect_args=connect_args, pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    """FastAPI-friendly session dependency."""
    engine = get_engine()
    with Session(engine) as session:
        yield session
