from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pandas as pd
import pytest

from cli.dca import _irr_bisect, main, simulate_dca


def _monthly_bars(prices: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2010-01-01", periods=len(prices), freq="MS", tz="UTC")
    return pd.DataFrame(
        {
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": [1_000_000] * len(prices),
        },
        index=idx,
    )


def test_simulate_flat_market_yields_break_even():
    bars = _monthly_bars([100.0] * 24)
    per_month, agg = simulate_dca(bars, monthly=1000.0, risk_free_annual=0.0)
    assert agg["n_months"] == 24
    assert agg["total_invested"] == pytest.approx(24_000)
    # at a flat 100, every $1000 buys 10 shares; final value should equal invested
    assert agg["final_value"] == pytest.approx(24_000)
    assert agg["total_return_pct"] == pytest.approx(0.0, abs=1e-9)
    # last row has cum_shares = 240, portfolio = 24000
    assert per_month["cum_shares"].iloc[-1] == pytest.approx(240.0)
    assert per_month["portfolio_value"].iloc[-1] == pytest.approx(24_000)


def test_simulate_monotone_up_produces_positive_return_and_cagr():
    # 24 months, price climbs from 100 → 200 linearly
    prices = [100.0 + (i * 100.0 / 23) for i in range(24)]
    bars = _monthly_bars(prices)
    _, agg = simulate_dca(bars, monthly=1000.0, risk_free_annual=0.02)
    assert agg["total_return_pct"] > 0
    assert agg["cagr"] is not None
    assert agg["cagr"] > 0
    # lump sum invested at start (price 100) doubles by end (price 200), so lump return ~+100%
    lump = agg["benchmark_lump_sum"]
    assert lump["total_return_pct"] == pytest.approx(1.0, abs=1e-6)
    # DCA averages in at higher prices on the way up → underperforms lump sum
    assert agg["dca_vs_lump_sum_delta_pct"] < 0


def test_simulate_known_two_period_result():
    # Two months, prices 100 then 200. Invest 1000 each.
    # Month 1: 10 shares.  Month 2: 5 shares.  Total invested 2000, shares 15.
    # Final value at 200 = 3000. Return = +50%.
    bars = _monthly_bars([100.0, 200.0])
    _, agg = simulate_dca(bars, monthly=1000.0, risk_free_annual=0.0)
    assert agg["total_invested"] == pytest.approx(2000.0)
    assert agg["final_value"] == pytest.approx(3000.0)
    assert agg["total_return_pct"] == pytest.approx(0.5, abs=1e-9)


def test_max_drawdown_detected():
    # up then crash
    bars = _monthly_bars([100, 110, 120, 60, 50, 55, 70, 80, 90, 100, 110, 120, 130])
    _, agg = simulate_dca(bars, monthly=1000.0, risk_free_annual=0.0)
    assert agg["max_drawdown_pct"] < -0.1


def test_irr_bisect_recovers_known_rate():
    # Deposit $100 at t=0, withdraw at t=11. r is the per-period IRR.
    r = 0.05
    n = 12  # cashflows at t=0..11; deposit grows for 11 periods
    final = 100 * (1 + r) ** (n - 1)
    cfs = [-100.0] + [0.0] * (n - 1)
    cfs[-1] += final
    import numpy as np

    out = _irr_bisect(np.array(cfs))
    assert out == pytest.approx(r, rel=1e-4)


def test_irr_bisect_returns_none_when_no_sign_change():
    import numpy as np

    # All negative — no root.
    assert _irr_bisect(np.array([-1.0, -1.0, -1.0])) is None


class _StubSource:
    def __init__(self, df: pd.DataFrame):
        self._df = df
        self.calls: list[tuple] = []

    def fetch(self, symbol, interval, start=None, end=None):
        self.calls.append((symbol, interval, start, end))
        return self._df


def test_cli_main_writes_csv_and_summary(tmp_path):
    bars = _monthly_bars([100.0, 110.0, 120.0, 130.0, 140.0, 150.0,
                          160.0, 170.0, 180.0, 190.0, 200.0, 210.0, 220.0])
    stub = _StubSource(bars)
    with patch("cli.dca._build_source", return_value=stub):
        rc = main([
            "--asset", "^NDX",
            "--start", "2010-01-01",
            "--monthly", "1000",
            "--output-dir", str(tmp_path),
        ])
    assert rc == 0
    csv = tmp_path / "dca-ndx.csv"
    summary = tmp_path / "dca-ndx.summary.json"
    assert csv.is_file()
    assert summary.is_file()
    import json
    data = json.loads(summary.read_text())
    assert data["asset"] == "^NDX"
    assert data["alpaca_symbol"] == "QQQ"
    assert data["n_months"] == 13


def test_cli_main_writes_dashboard_json(tmp_path):
    prices = [100.0 + 5 * i for i in range(15)]
    stub = _StubSource(_monthly_bars(prices))
    with patch("cli.dca._build_source", return_value=stub):
        rc = main([
            "--asset", "^NDX",
            "--start", "2010-01-01",
            "--monthly", "1000",
            "--output-dir", str(tmp_path),
        ])
    assert rc == 0
    import json
    dash = json.loads((tmp_path / "dca-ndx.dashboard.json").read_text())
    assert dash["schema_version"] == 1
    assert dash["asset"] == "^NDX"
    assert len(dash["series"]) == 15
    first, last = dash["series"][0], dash["series"][-1]
    assert {"month", "cum_invested", "dca_value", "lump_value"} == first.keys()
    # cumulative invested grows by `monthly` each step.
    assert last["cum_invested"] == pytest.approx(15_000)
    # lump-sum buys all shares at the first (cheapest) bar, so on a rising market
    # its terminal equity beats the dollar-cost-averaged book.
    assert last["lump_value"] > last["dca_value"]


def test_cli_main_rejects_insufficient_history(tmp_path):
    bars = _monthly_bars([100.0, 105.0, 110.0])  # only 3 bars
    stub = _StubSource(bars)
    with patch("cli.dca._build_source", return_value=stub):
        rc = main([
            "--asset", "QQQ",
            "--start", "2010-01-01",
            "--output-dir", str(tmp_path),
        ])
    assert rc != 0


def test_cli_main_rejects_unknown_source(tmp_path):
    with pytest.raises(SystemExit):
        main([
            "--asset", "QQQ",
            "--start", "2010-01-01",
            "--source", "yfinance",
            "--output-dir", str(tmp_path),
        ])


def test_cli_main_records_truncation_warning(tmp_path):
    # Asks for 1996 but bars start in 2010 → warning recorded.
    bars = _monthly_bars([100.0 + i for i in range(15)])
    stub = _StubSource(bars)
    with patch("cli.dca._build_source", return_value=stub):
        rc = main([
            "--asset", "^NDX",
            "--start", "1996-01-01",
            "--output-dir", str(tmp_path),
        ])
    assert rc == 0
    import json
    data = json.loads((tmp_path / "dca-ndx.summary.json").read_text())
    assert "history_truncation_warning" in data


def test_cli_passes_correct_args_to_source(tmp_path):
    bars = _monthly_bars([100.0 + i for i in range(15)])
    stub = _StubSource(bars)
    with patch("cli.dca._build_source", return_value=stub):
        main([
            "--asset", "^NDX",
            "--start", "2015-01-01",
            "--end", "2020-12-31",
            "--monthly", "500",
            "--output-dir", str(tmp_path),
        ])
    (sym, interval, start, end) = stub.calls[0]
    assert sym == "^NDX"  # CLI passes raw symbol, source does the mapping
    assert interval == "1mo"
    assert start == datetime(2015, 1, 1, tzinfo=UTC)
    assert end == datetime(2020, 12, 31, tzinfo=UTC)
