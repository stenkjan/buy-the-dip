from __future__ import annotations

import numpy as np
import pandas as pd

from bot_core.backtest import compare_dca, run_backtest, simulate_dca, simulate_strategy
from bot_core.backtest.dca import first_trading_day_of_month
from bot_core.types import Signal
from strategies.buy_the_dip import get_strategy


def _synthetic_daily(n: int = 3500, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0006, 0.010, n)
    for start in (1700, 2400, 3000):
        rets[start : start + 40] = -0.022
    price = 100 * np.exp(np.cumsum(rets))
    idx = pd.date_range("2014-01-01", periods=n, freq="1D", tz="UTC")
    return pd.DataFrame(
        {"open": price, "high": price * 1.005, "low": price * 0.995, "close": price, "volume": 1.0},
        index=idx,
    )


def test_first_trading_day_of_month_picks_one_bar_per_month():
    idx = pd.date_range("2020-01-01", periods=400, freq="1D", tz="UTC")
    firsts = first_trading_day_of_month(idx)
    # 400 days spans 14 calendar months (Jan 2020 .. Feb 2021).
    assert len(firsts) == 14
    # Each pick is the 1st of its month here (no gaps in a daily range).
    assert all(ts.day == 1 for ts in firsts)


def test_dca_units_match_total_invested_at_flat_price():
    idx = pd.date_range("2020-01-01", periods=400, freq="1D", tz="UTC")
    closes = pd.Series(100.0, index=idx)
    dates = first_trading_day_of_month(idx)
    res = simulate_dca(closes, dates, monthly_contribution=1000.0)
    # Flat price ⇒ final value equals everything contributed, zero profit.
    assert res.n_buys == len(dates)
    assert res.final_value == res.total_invested
    assert abs(res.total_return) < 1e-12


def test_strategy_holds_cash_when_no_signal_fires():
    idx = pd.date_range("2020-01-01", periods=400, freq="1D", tz="UTC")
    closes = pd.Series(100.0, index=idx)
    dates = first_trading_day_of_month(idx)
    res = simulate_strategy(
        closes, signals=[], contribution_dates=dates, monthly_contribution=1000.0
    )
    # No signals ⇒ everything stays in cash; value == contributions, nothing bought.
    assert res.n_buys == 0
    assert abs(res.ending_cash - res.total_invested) < 1e-9
    assert abs(res.final_value - res.total_invested) < 1e-9


def test_strategy_deploys_tranche_on_signal():
    idx = pd.date_range("2020-01-01", periods=400, freq="1D", tz="UTC")
    closes = pd.Series(100.0, index=idx)
    dates = first_trading_day_of_month(idx)
    sig = Signal(
        symbol="X",
        timestamp=idx[40].to_pydatetime(),
        triggered=True,
        stufe=2,
        rsi_value=20.0,
        rsi_threshold=30.0,
        price=100.0,
        tranche_pct_range=(20.0, 40.0),  # midpoint 30%
    )
    res = simulate_strategy(closes, [sig], dates, monthly_contribution=1000.0)
    assert res.n_buys == 1
    # By bar 40 two contributions have landed (Jan 1 + Feb 1) ⇒ cash 2000, deploy 30%.
    assert res.ending_cash < res.total_invested  # some cash was put to work


def test_compare_dca_keys_and_consistency():
    daily = _synthetic_daily()
    result = run_backtest("SYN", daily, get_strategy())
    report = compare_dca(
        "SYN", result.indicators["close"], result.signals, monthly_contribution=500.0
    )

    assert set(report) == {
        "symbol",
        "period",
        "monthly_contribution",
        "n_contributions",
        "total_invested",
        "risk_free_annual",
        "strategy",
        "dca",
        "delta",
    }
    for leg in ("strategy", "dca"):
        assert {
            "final_value",
            "total_invested",
            "profit",
            "total_return",
            "irr_annual",
            "cagr_twr",
            "sharpe",
            "volatility_annual",
            "max_drawdown",
            "n_buys",
            "ending_cash",
        }.issubset(report[leg])
    # Both legs receive the identical contribution stream.
    assert report["strategy"]["total_invested"] == report["dca"]["total_invested"]
    assert report["total_invested"] == report["monthly_contribution"] * report["n_contributions"]


def test_compare_dca_handles_empty_history():
    empty = pd.Series([], dtype=float)
    report = compare_dca("SYN", empty, [])
    assert "error" in report
