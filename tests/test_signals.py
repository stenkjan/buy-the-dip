from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from bot_core.types import AssetData
from strategies.buy_the_dip import BuyTheDipConfig, get_strategy


def _data(
    close: float, ema_d: float, ema_w: float, rsi12: float, rsi1d: float, rsi1w: float
) -> AssetData:
    return AssetData(
        symbol="^NDX",
        timestamp=datetime(2026, 5, 28, tzinfo=UTC),
        last_close=close,
        ema200_daily=ema_d,
        ema200_weekly=ema_w,
        rsi_12h=rsi12,
        rsi_1d=rsi1d,
        rsi_1w=rsi1w,
    )


def test_stufe1_uses_12h_rsi_and_strict_threshold():
    strat = get_strategy(BuyTheDipConfig(liberal=False))
    sig = strat.evaluate(_data(close=100, ema_d=90, ema_w=80, rsi12=29, rsi1d=70, rsi1w=70))
    assert sig.stufe == 1
    assert sig.rsi_threshold == 30.0
    assert sig.triggered is True


def test_stufe2_between_emas_uses_1d_rsi_with_liberal_threshold():
    strat = get_strategy(BuyTheDipConfig(liberal=True))
    sig = strat.evaluate(_data(close=85, ema_d=90, ema_w=80, rsi12=70, rsi1d=30.3, rsi1w=70))
    assert sig.stufe == 2
    assert sig.rsi_threshold == 30.5
    assert sig.triggered is True


def test_stufe3_below_weekly_ema_uses_1w_rsi():
    strat = get_strategy(BuyTheDipConfig(liberal=True))
    sig = strat.evaluate(_data(close=70, ema_d=90, ema_w=80, rsi12=70, rsi1d=70, rsi1w=31.9))
    assert sig.stufe == 3
    assert sig.rsi_threshold == 32.0
    assert sig.triggered is True


def test_no_trigger_when_rsi_above_threshold():
    strat = get_strategy()
    sig = strat.evaluate(_data(close=100, ema_d=90, ema_w=80, rsi12=45, rsi1d=70, rsi1w=70))
    assert sig.triggered is False


def _history_with_recent_crash(now_above: bool) -> pd.DataFrame:
    """Build a synthetic AssetData.history that crashed under weekly EMA then recovered."""
    n = 40
    idx = pd.date_range("2024-01-01", periods=n, freq="1D", tz="UTC")
    # First 20 bars: close BELOW ema_weekly. Last 20 bars: close ABOVE both EMAs.
    closes = [80.0] * 20 + [95.0] * 20
    if not now_above:
        # Override: the LAST bar is back below — current price is below ema_d
        closes[-1] = 70.0
    return pd.DataFrame(
        {"close": closes, "ema200_daily": [90.0] * n, "ema200_weekly": [85.0] * n},
        index=idx,
    )


def test_macro_reclaim_fires_after_below_weekly_then_above_both():
    strat = get_strategy(BuyTheDipConfig(liberal=True, macro_reclaim_window_weeks=8))
    history = _history_with_recent_crash(now_above=True)
    data = AssetData(
        symbol="^NDX",
        timestamp=datetime(2026, 5, 28, tzinfo=UTC),
        last_close=100.0,
        ema200_daily=90.0,
        ema200_weekly=85.0,
        rsi_12h=33.0,  # would NOT trigger strict (30) but WOULD trigger liberal (35)
        rsi_1d=70.0,
        rsi_1w=70.0,
        history=history,
    )
    sig = strat.evaluate(data)
    assert sig.stufe == 1
    assert sig.rsi_threshold == 35.0
    assert sig.triggered is True
    assert sig.extras["macro_reclaim"] is True


def test_macro_reclaim_does_not_fire_without_prior_crash():
    strat = get_strategy(BuyTheDipConfig(liberal=True))
    n = 40
    idx = pd.date_range("2024-01-01", periods=n, freq="1D", tz="UTC")
    history = pd.DataFrame(
        {"close": [95.0] * n, "ema200_daily": [90.0] * n, "ema200_weekly": [85.0] * n},
        index=idx,
    )
    data = AssetData(
        symbol="^NDX",
        timestamp=datetime(2026, 5, 28, tzinfo=UTC),
        last_close=100.0,
        ema200_daily=90.0,
        ema200_weekly=85.0,
        rsi_12h=33.0,
        rsi_1d=70.0,
        rsi_1w=70.0,
        history=history,
    )
    sig = strat.evaluate(data)
    assert sig.stufe == 1
    assert sig.rsi_threshold == 30.0  # strict — macro_reclaim did not fire
    assert sig.triggered is False
    assert sig.extras["macro_reclaim"] is False


def test_macro_reclaim_disabled_without_history():
    strat = get_strategy(BuyTheDipConfig(liberal=True))
    data = _data(close=100, ema_d=90, ema_w=80, rsi12=33, rsi1d=70, rsi1w=70)
    sig = strat.evaluate(data)
    assert sig.rsi_threshold == 30.0
    assert sig.extras["macro_reclaim"] is False


def test_tranche_recommendation_matches_stufe():
    strat = get_strategy()
    s1 = strat.evaluate(_data(100, 90, 80, 29, 70, 70))
    s2 = strat.evaluate(_data(85, 90, 80, 70, 29, 70))
    s3 = strat.evaluate(_data(70, 90, 80, 70, 70, 29))
    assert s1.tranche_pct_range == (10.0, 20.0)
    assert s2.tranche_pct_range == (20.0, 40.0)
    assert s3.tranche_pct_range == (40.0, 60.0)
