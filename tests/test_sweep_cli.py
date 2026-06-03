from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
from sqlmodel import select

from bot_core.db.models import ParameterRun
from cli import sweep as sweep_cli


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


def test_run_persists_parameter_runs(db_session, monkeypatch):
    monkeypatch.setattr(sweep_cli, "YFinanceSource", lambda: _StubSource())
    written = sweep_cli.run(db_session, ["^NDX"], start=datetime(2018, 1, 1))
    assert written == 3  # default grid has 3 entries
    rows = db_session.exec(select(ParameterRun)).all()
    assert len(rows) == 3
    assert all(r.strategy_name == "buy_the_dip" for r in rows)
    assert all(r.total_signals >= 0 for r in rows)


def test_run_skips_short_history(db_session, monkeypatch):
    class _Short:
        def fetch(self, *a, **k):
            return _daily(50)

    monkeypatch.setattr(sweep_cli, "YFinanceSource", lambda: _Short())
    written = sweep_cli.run(db_session, ["^NDX"], start=datetime(2018, 1, 1))
    assert written == 0
    assert db_session.exec(select(ParameterRun)).all() == []
