from __future__ import annotations

import json
from unittest.mock import patch

import numpy as np
import pandas as pd

from cli import history as history_cli
from cli.history import build_timeline, main


def _daily_with_crash(n: int = 1600) -> pd.DataFrame:
    """Long uptrend with a sharp drawdown near the end → guaranteed triggers."""
    idx = pd.date_range("2018-01-01", periods=n, freq="D", tz="UTC")
    close = np.linspace(100.0, 320.0, n)
    close[-40:] = close[-41] * 0.55  # deep crash → low RSI across Stufen
    return pd.DataFrame(
        {"open": close, "high": close, "low": close, "close": close,
         "volume": [1_000_000] * n},
        index=idx,
    )


def test_build_timeline_shape_and_signals():
    payload = build_timeline("^NDX", _daily_with_crash(), liberal=True)
    assert payload["schema_version"] == 1
    assert payload["asset"] == "^NDX"
    assert payload["liberal"] is True
    assert payload["n_bars"] > 0
    assert payload["summary"]["total"] >= 1
    assert payload["signals"], "engineered crash should produce triggered signals"
    s0 = payload["signals"][0]
    expected = {"timestamp", "symbol", "stufe", "rsi_value", "rsi_threshold", "price"}
    assert expected <= s0.keys()
    # forward-return columns are present (NaN serialises to None for late bars).
    assert any(k.startswith("fwd_") for k in s0)


class _StubSource:
    def __init__(self, df: pd.DataFrame):
        self._df = df

    def fetch(self, symbol, interval, start=None, end=None):
        return self._df


def test_cli_main_writes_timeline_json(tmp_path):
    with patch.object(history_cli, "YFinanceSource", lambda: _StubSource(_daily_with_crash())):
        rc = main(["--asset", "^GSPC", "--start", "2018-01-01", "--output-dir", str(tmp_path)])
    assert rc == 0
    payload = json.loads((tmp_path / "gspc.timeline.json").read_text())
    assert payload["asset"] == "^GSPC"
    assert payload["summary"]["total"] >= 1


def test_cli_main_rejects_short_history(tmp_path):
    with patch.object(history_cli, "YFinanceSource", lambda: _StubSource(_daily_with_crash(100))):
        rc = main(["--asset", "^NDX", "--output-dir", str(tmp_path)])
    assert rc != 0
