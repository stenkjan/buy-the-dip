from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.api.main import create_app  # noqa: E402
from apps.api.routers import sweep as sweep_router  # noqa: E402
from bot_core.db import models  # noqa: E402,F401
from bot_core.db.models import ParameterRun  # noqa: E402
from bot_core.db.session import get_session  # noqa: E402

H = {"X-API-Key": "secret"}


def _daily(n: int = 1600) -> pd.DataFrame:
    idx = pd.date_range("2018-01-01", periods=n, freq="D", tz="UTC")
    close = np.linspace(100.0, 320.0, n)
    close[-40:] = close[-41] * 0.55
    return pd.DataFrame(
        {"open": close, "high": close, "low": close, "close": close,
         "volume": [1_000_000] * n},
        index=idx,
    )


class _StubSource:
    def fetch(self, symbol, interval, start=None, end=None):
        return _daily()


@pytest.fixture
def engine():
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


def test_sweep_requires_key(engine, monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    assert _client(engine).post("/parameter-sweep", json={"asset": "^NDX"}).status_code == 401


def test_sweep_ranks_and_persists(engine, monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setattr(sweep_router, "YFinanceSource", lambda: _StubSource())
    client = _client(engine)

    r = client.post("/parameter-sweep", headers=H, json={"asset": "^NDX", "persist": True})
    assert r.status_code == 200
    body = r.json()
    assert body["asset"] == "^NDX" and body["horizon"] == "fwd_90d"
    assert len(body["results"]) == 3
    assert "params" in body["results"][0]

    # persist=True wrote a ParameterRun per grid entry
    with Session(engine) as s:
        runs = s.exec(select(ParameterRun)).all()
    assert len(runs) == 3
    assert all(run.strategy_name == "buy_the_dip" for run in runs)
