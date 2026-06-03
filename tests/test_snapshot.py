from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bot_core.types import AssetData
from cli import _common
from cli import snapshot as snapshot_cli
from strategies.buy_the_dip import BuyTheDipConfig


def _fake_asset_data(symbol: str) -> AssetData:
    return AssetData(
        symbol=symbol,
        timestamp=datetime(2026, 5, 28, tzinfo=UTC),
        last_close=100.0,
        ema200_daily=90.0,
        ema200_weekly=80.0,
        rsi_12h=29.0,
        rsi_1d=70.0,
        rsi_1w=70.0,
    )


def test_snapshot_writes_payload_with_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def fake_snapshot(symbol: str):
        return _fake_asset_data(symbol)

    monkeypatch.setattr(snapshot_cli, "snapshot_asset", fake_snapshot)

    out = tmp_path / "signals.json"
    code = snapshot_cli.main(["--output", str(out)])
    assert code == 0
    payload = json.loads(out.read_text())

    assert payload["schema_version"] == snapshot_cli.SCHEMA_VERSION
    assert datetime.fromisoformat(payload["generated_at"]).tzinfo is not None
    assert len(payload["signals"]) == 2  # ^NDX and ^GSPC from default config
    s0 = payload["signals"][0]
    assert {"symbol", "stufe", "rsi_value", "rsi_threshold", "triggered", "price"} <= s0.keys()


def test_snapshot_skips_assets_without_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(snapshot_cli, "snapshot_asset", lambda symbol: None)

    out = tmp_path / "signals.json"
    code = snapshot_cli.main(["--output", str(out)])
    assert code == 0
    payload = json.loads(out.read_text())
    assert payload["signals"] == []


class _FakeSource:
    """Stand-in for YFinanceSource returning a deterministic daily series."""

    def __init__(self, daily: pd.DataFrame) -> None:
        self._daily = daily

    def fetch(self, symbol: str, interval: str) -> pd.DataFrame:
        return self._daily


def _synthetic_daily(n: int = 1600) -> pd.DataFrame:
    """Rising trend with a sharp dip near the end so a Stufe trigger appears.

    Needs enough bars for a weekly EMA200 (≥200 weeks ≈ 1400 daily bars).
    """
    idx = pd.date_range("2018-01-01", periods=n, freq="D", tz="UTC")
    close = np.linspace(100.0, 300.0, n)
    close[-15:] = close[-16] * 0.6  # ~40% crash → low RSI, below EMA
    return pd.DataFrame({"close": close}, index=idx)


def test_build_history_shape_and_columns(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(_common, "YFinanceSource", lambda: _FakeSource(_synthetic_daily()))

    rows = _common.build_history("^NDX", BuyTheDipConfig(), bars=120)
    assert rows is not None
    assert len(rows) == 120
    expected = {
        "timestamp", "close", "ema200_daily", "ema200_weekly",
        "rsi_1d", "rsi_1w", "stufe", "triggered",
    }
    assert expected <= rows[0].keys()
    # The engineered crash at the tail must produce at least one trigger marker.
    assert any(r["triggered"] for r in rows)
    assert all(r["stufe"] in (1, 2, 3) for r in rows)


def test_build_history_returns_none_for_short_series(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(_common, "YFinanceSource", lambda: _FakeSource(_synthetic_daily(50)))
    assert _common.build_history("^NDX", BuyTheDipConfig()) is None


def test_snapshot_writes_history_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(snapshot_cli, "snapshot_asset", lambda symbol: _fake_asset_data(symbol))

    def fake_history(symbol, config, bars=500):
        return [
            {
                "timestamp": "2026-05-28T00:00:00+00:00",
                "close": 100.0, "ema200_daily": 90.0, "ema200_weekly": 80.0,
                "rsi_1d": 29.0, "rsi_1w": 40.0, "stufe": 1, "triggered": True,
            }
        ]

    monkeypatch.setattr(snapshot_cli, "build_history", fake_history)

    out = tmp_path / "signals.json"
    hist = tmp_path / "history.json"
    code = snapshot_cli.main(
        ["--output", str(out), "--history-output", str(hist), "--history-bars", "10"]
    )
    assert code == 0
    payload = json.loads(hist.read_text())
    assert payload["schema_version"] == snapshot_cli.HISTORY_SCHEMA_VERSION
    assert set(payload["assets"]) == {"^NDX", "^GSPC"}
    assert payload["assets"]["^NDX"][0]["triggered"] is True
    # signals.json and history.json share the same generation timestamp.
    assert payload["generated_at"] == json.loads(out.read_text())["generated_at"]
