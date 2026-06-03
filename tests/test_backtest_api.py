from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.api.main import create_app  # noqa: E402
from apps.api.routers import backtest as backtest_router  # noqa: E402

H = {"X-API-Key": "secret"}


def _synthetic_daily(n: int = 1600) -> pd.DataFrame:
    idx = pd.date_range("2018-01-01", periods=n, freq="D", tz="UTC")
    close = np.linspace(100.0, 320.0, n)
    close[-40:] = close[-41] * 0.55  # crash → triggers
    return pd.DataFrame(
        {"open": close, "high": close, "low": close, "close": close,
         "volume": [1_000_000] * n},
        index=idx,
    )


class _StubSource:
    def fetch(self, symbol, interval, start=None, end=None):
        return _synthetic_daily()


def _client():
    from fastapi.testclient import TestClient

    return TestClient(create_app())


def test_backtest_requires_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    r = _client().post("/backtest", json={"asset": "^NDX"})
    assert r.status_code == 401


def test_backtest_disabled_without_key(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    r = _client().post("/backtest", headers=H, json={"asset": "^NDX"})
    assert r.status_code == 503


def test_backtest_runs_with_thresholds(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setattr(backtest_router, "YFinanceSource", lambda: _StubSource())
    r = _client().post(
        "/backtest", headers=H,
        json={"asset": "^NDX", "config": {"rsi_threshold_stufe1": 35, "liberal": False}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["asset"] == "^NDX"
    assert body["liberal"] is False
    assert body["n_bars"] > 0
    assert body["summary"]["total"] >= 1
    assert body["signals"]
    s0 = body["signals"][0]
    assert {"timestamp", "stufe", "rsi_value", "rsi_threshold", "price"} <= s0.keys()
