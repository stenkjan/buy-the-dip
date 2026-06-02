from __future__ import annotations

import pytest

from bot_core.db.session import (
    DEFAULT_SQLITE_URL,
    normalize_database_url,
    resolve_database_url,
)


@pytest.mark.parametrize(
    "input_url, expected",
    [
        (
            "postgresql://user:pw@host:5432/db",
            "postgresql+psycopg://user:pw@host:5432/db",
        ),
        (
            "postgres://user:pw@host:5432/db?sslmode=require",
            "postgresql+psycopg://user:pw@host:5432/db?sslmode=require",
        ),
        (
            "postgresql+psycopg://user@host/db",
            "postgresql+psycopg://user@host/db",
        ),
        (
            "sqlite:///./buythedip.db",
            "sqlite:///./buythedip.db",
        ),
    ],
)
def test_normalize_database_url(input_url: str, expected: str) -> None:
    assert normalize_database_url(input_url) == expected


def test_resolve_database_url_falls_back_to_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    monkeypatch.delenv("POSTGRES_URL_NON_POOLING", raising=False)
    assert resolve_database_url() == DEFAULT_SQLITE_URL


def test_resolve_database_url_normalizes_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_URL", "postgres://user@host/db")
    monkeypatch.delenv("POSTGRES_URL_NON_POOLING", raising=False)
    assert resolve_database_url() == "postgresql+psycopg://user@host/db"


def test_resolve_database_url_prefers_non_pooling_when_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES_URL", "postgres://pooled@host/db")
    monkeypatch.setenv("POSTGRES_URL_NON_POOLING", "postgres://direct@host/db")
    assert resolve_database_url(prefer_non_pooling=True) == "postgresql+psycopg://direct@host/db"
    assert resolve_database_url() == "postgresql+psycopg://pooled@host/db"
