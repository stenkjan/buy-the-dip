from __future__ import annotations

import numpy as np
import pandas as pd

from bot_core.indicators import ema, resample_ohlc, rsi_wilder


def test_rsi_wilder_returns_100_when_only_gains():
    closes = pd.Series(range(1, 50), dtype=float)
    r = rsi_wilder(closes, length=14).dropna()
    assert r.iloc[-1] == 100.0


def test_rsi_wilder_in_bounds():
    rng = np.random.default_rng(42)
    closes = pd.Series(100 + rng.standard_normal(200).cumsum())
    r = rsi_wilder(closes, length=14).dropna()
    assert ((r >= 0) & (r <= 100)).all()


def test_ema_length():
    s = pd.Series(np.linspace(1, 100, 300))
    out = ema(s, length=200)
    assert out.isna().iloc[:199].all()
    assert not out.isna().iloc[-1]


def test_resample_ohlc_aggregation():
    idx = pd.date_range("2024-01-01", periods=48, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "open": np.arange(48, dtype=float),
            "high": np.arange(48, dtype=float) + 0.5,
            "low": np.arange(48, dtype=float) - 0.5,
            "close": np.arange(48, dtype=float) + 0.25,
            "volume": np.ones(48),
        },
        index=idx,
    )
    out = resample_ohlc(df, "12h")
    assert 4 <= len(out) <= 5
    assert (out["high"] >= out["low"]).all()
    assert out["volume"].sum() == 48
