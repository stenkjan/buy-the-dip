from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bot_core.types import AssetData
from cli import snapshot as snapshot_cli


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
