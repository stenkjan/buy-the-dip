from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.api.main import create_app  # noqa: E402

H = {"X-API-Key": "secret"}


def test_api_bootstraps_sqlite_tables(tmp_path, monkeypatch):
    """A fresh SQLite file should work end-to-end without a manual create_all:
    the lifespan startup hook creates the tables."""
    from fastapi.testclient import TestClient

    db = tmp_path / "fresh.db"
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("POSTGRES_URL", "")
    monkeypatch.setenv("POSTGRES_URL_NON_POOLING", "")
    # point the (lru_cached) engine resolver at a brand-new sqlite file
    import bot_core.db.session as db_session
    db_session.get_engine.cache_clear()
    monkeypatch.setattr(db_session, "DEFAULT_SQLITE_URL", f"sqlite:///{db}")

    # TestClient as a context manager runs lifespan (startup → create tables)
    with TestClient(create_app()) as client:
        r = client.post("/bots", headers=H, json={"name": "ndx", "asset_symbol": "^NDX"})
        assert r.status_code == 201
        assert len(client.get("/bots", headers=H).json()) == 1

    db_session.get_engine.cache_clear()
