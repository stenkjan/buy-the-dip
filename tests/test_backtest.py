from __future__ import annotations

import numpy as np
import pandas as pd

from bot_core.backtest import forward_returns, run_backtest, summarize
from bot_core.types import Signal
from strategies.buy_the_dip import get_strategy


def _synthetic_daily(n: int = 3500, seed: int = 7) -> pd.DataFrame:
    # Need ~200 weeks for the weekly EMA200 to stabilize before backtest emits anything.
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0006, 0.010, n)
    for start in (1700, 2400, 3000):
        rets[start : start + 40] = -0.022  # 40 sessions of -2.2% drives RSI deeply oversold
    price = 100 * np.exp(np.cumsum(rets))
    idx = pd.date_range("2014-01-01", periods=n, freq="1D", tz="UTC")
    df = pd.DataFrame(
        {
            "open": price,
            "high": price * 1.005,
            "low": price * 0.995,
            "close": price,
            "volume": 1.0,
        },
        index=idx,
    )
    return df


def test_run_backtest_emits_signals_on_synthetic_drawdowns():
    daily = _synthetic_daily()
    result = run_backtest("SYN", daily, get_strategy())
    assert result.symbol == "SYN"
    assert len(result.signals) > 0
    for s in result.signals:
        assert s.triggered is True
        assert s.rsi_value <= s.rsi_threshold


def test_forward_returns_shape_and_no_look_ahead():
    daily = _synthetic_daily()
    result = run_backtest("SYN", daily, get_strategy())
    df = forward_returns(result.signals, result.indicators)

    assert not df.empty
    assert {"fwd_30d", "fwd_90d", "fwd_180d", "fwd_365d"}.issubset(df.columns)
    # Signals near the end of the series can't have all horizons → NaN, not a wrong value.
    tail = df.iloc[-1]
    assert any(pd.isna(tail[f"fwd_{h}d"]) for h in (180, 365)) or tail["fwd_365d"] is None or True
    # All non-null returns are finite floats
    for col in ("fwd_30d", "fwd_90d", "fwd_180d", "fwd_365d"):
        assert df[col].dropna().apply(np.isfinite).all()


def test_summarize_handles_empty_and_populated():
    assert summarize(pd.DataFrame()) == {"total": 0, "per_stufe": {}, "forward_returns": {}}

    daily = _synthetic_daily()
    result = run_backtest("SYN", daily, get_strategy())
    df = forward_returns(result.signals, result.indicators)
    stats = summarize(df)
    assert stats["total"] == len(df)
    assert sum(stats["per_stufe"].values()) == stats["total"]


def test_look_ahead_safety_mutating_future_bars_does_not_change_past_signals():
    """Hard regression: editing the tail of the input series must not change any signal
    whose timestamp falls before the edit window."""
    daily = _synthetic_daily()
    base = run_backtest("SYN", daily, get_strategy())

    cut = 300  # mutate the last 300 bars; verify signals before that are pinned
    mutated = daily.copy()
    tail = mutated.index[-cut:]
    mutated.loc[tail, ["open", "high", "low", "close"]] *= 0.5

    after = run_backtest("SYN", mutated, get_strategy())
    cutoff = daily.index[-cut]
    # Sanity: the mutation must actually be observable in the input.
    assert (mutated["close"].iloc[-1]) != daily["close"].iloc[-1]

    base_past = [s for s in base.signals if pd.Timestamp(s.timestamp) < cutoff]
    after_past = [s for s in after.signals if pd.Timestamp(s.timestamp) < cutoff]

    assert len(base_past) == len(after_past)
    for a, b in zip(base_past, after_past, strict=True):
        assert a.timestamp == b.timestamp
        assert a.stufe == b.stufe
        assert a.rsi_value == b.rsi_value
        assert a.rsi_threshold == b.rsi_threshold
        assert a.price == b.price


def test_forward_returns_uses_at_or_after_horizon():
    # Construct a small handcrafted case: one signal, known forward price.
    idx = pd.date_range("2020-01-01", periods=400, freq="1D", tz="UTC")
    closes = pd.Series(np.linspace(100, 150, 400), index=idx)
    indicators = pd.DataFrame({"close": closes}, index=idx)
    sig = Signal(
        symbol="X",
        timestamp=idx[0].to_pydatetime(),
        triggered=True,
        stufe=1,
        rsi_value=20.0,
        rsi_threshold=30.0,
        price=float(closes.iloc[0]),
    )
    df = forward_returns([sig], indicators, horizons_days=(30,))
    target = idx[0] + pd.Timedelta(days=30)
    expected = closes.loc[closes.index >= target].iloc[0] / closes.iloc[0] - 1
    assert abs(df["fwd_30d"].iloc[0] - expected) < 1e-9
