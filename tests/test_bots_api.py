from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.api.main import create_app  # noqa: E402
from bot_core.db import models  # noqa: E402,F401 — registers tables
from bot_core.db.session import get_session  # noqa: E402

H = {"X-API-Key": "secret"}


@pytest.fixture
def engine():
    # StaticPool keeps one connection so the in-memory DB survives across the
    # per-request sessions opened by the dependency override.
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(eng)
    return eng


def _client(engine):
    from fastapi.testclient import TestClient

    app = create_app()

    def _override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override
    return TestClient(app)


def test_admin_disabled_without_api_key(engine, monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    client = _client(engine)
    r = client.get("/bots")
    assert r.status_code == 503


def test_rejects_wrong_key(engine, monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    client = _client(engine)
    assert client.get("/bots", headers={"X-API-Key": "nope"}).status_code == 401
    assert client.get("/bots").status_code == 401


def test_bot_crud_flow(engine, monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    client = _client(engine)

    r = client.post("/bots", headers=H, json={"name": "ndx", "asset_symbol": "^NDX"})
    assert r.status_code == 201
    bot = r.json()
    bid = bot["id"]
    assert bot["mode"] == "paper" and bot["enabled"] is False

    assert len(client.get("/bots", headers=H).json()) == 1

    r = client.post(f"/bots/{bid}/toggle", headers=H)
    assert r.json()["enabled"] is True
    assert len(client.get("/bots?enabled_only=true", headers=H).json()) == 1

    r = client.patch(f"/bots/{bid}", headers=H, json={"mode": "live", "config_json": {"x": 1}})
    assert r.json()["mode"] == "live"
    assert r.json()["config_json"] == {"x": 1}

    assert client.get(f"/bots/{bid}/signals", headers=H).json() == []
    assert client.get(f"/bots/{bid}/positions", headers=H).json() == []

    assert client.get("/bots/does-not-exist", headers=H).status_code == 404

    assert client.delete(f"/bots/{bid}", headers=H).status_code == 204
    assert client.get("/bots", headers=H).json() == []


def test_emergency_stop_pauses_bots(engine, monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    client = _client(engine)
    # an enabled bot with no open orders → broker is never needed
    bid = client.post("/bots", headers=H, json={"name": "ndx", "asset_symbol": "^NDX"}).json()["id"]
    client.post(f"/bots/{bid}/toggle", headers=H)  # enable
    assert client.get(f"/bots/{bid}", headers=H).json()["enabled"] is True

    r = client.post("/emergency-stop", headers=H)
    assert r.status_code == 200
    body = r.json()
    assert body["bots_paused"] == 1 and body["orders_cancelled"] == 0
    assert client.get(f"/bots/{bid}", headers=H).json()["enabled"] is False


def test_create_rejects_invalid_mode(engine, monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    client = _client(engine)
    r = client.post(
        "/bots", headers=H, json={"name": "x", "asset_symbol": "^NDX", "mode": "yolo"}
    )
    assert r.status_code == 422
