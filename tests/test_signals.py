from __future__ import annotations

from datetime import UTC, datetime

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


def test_tranche_recommendation_matches_stufe():
    strat = get_strategy()
    s1 = strat.evaluate(_data(100, 90, 80, 29, 70, 70))
    s2 = strat.evaluate(_data(85, 90, 80, 70, 29, 70))
    s3 = strat.evaluate(_data(70, 90, 80, 70, 70, 29))
    assert s1.tranche_pct_range == (10.0, 20.0)
    assert s2.tranche_pct_range == (20.0, 40.0)
    assert s3.tranche_pct_range == (40.0, 60.0)
