from __future__ import annotations

from bot_core.types import AssetData, Signal

from .config import BuyTheDipConfig


class BuyTheDipStrategy:
    name = "buy_the_dip"

    def __init__(self, config: BuyTheDipConfig | None = None) -> None:
        self.config = config or BuyTheDipConfig()

    def evaluate(self, data: AssetData) -> Signal:
        c = self.config
        close, ema_d, ema_w = data.last_close, data.ema200_daily, data.ema200_weekly

        if close > ema_d:
            stufe, rsi, thr = 1, data.rsi_12h, c.rsi_threshold_stufe1
            if c.liberal and self._macro_reclaim(data):
                thr = c.rsi_threshold_stufe1_liberal
            tranche = c.tranche_stufe1
        elif close > ema_w:
            stufe, rsi, thr = 2, data.rsi_1d, c.rsi_threshold_stufe2
            if c.liberal:
                thr = c.rsi_threshold_stufe2_liberal
            tranche = c.tranche_stufe2
        else:
            stufe, rsi, thr = 3, data.rsi_1w, c.rsi_threshold_stufe3
            if c.liberal:
                thr = c.rsi_threshold_stufe3_liberal
            tranche = c.tranche_stufe3

        return Signal(
            symbol=data.symbol,
            timestamp=data.timestamp,
            triggered=rsi <= thr,
            stufe=stufe,
            rsi_value=float(rsi),
            rsi_threshold=float(thr),
            price=float(close),
            tranche_pct_range=tranche,
            extras={"macro_reclaim": stufe == 1 and thr == c.rsi_threshold_stufe1_liberal},
        )

    def _macro_reclaim(self, data: AssetData) -> bool:
        """True iff price was below EMA200_weekly within the configured lookback window
        AND has now reclaimed both EMA200_daily and EMA200_weekly. Conservative —
        disabled when history is missing or columns aren't named as expected.
        """
        if data.history is None:
            return False
        needed = {"close", "ema200_daily", "ema200_weekly"}
        if not needed.issubset(data.history.columns):
            return False
        now_above_both = (
            data.last_close > data.ema200_daily and data.last_close > data.ema200_weekly
        )
        if not now_above_both:
            return False
        window_bars = self.config.macro_reclaim_window_weeks * 5
        hist = data.history.tail(window_bars)
        if len(hist) < window_bars // 2:
            return False  # not enough history to reliably detect the reclaim
        was_below_weekly = (hist["close"] < hist["ema200_weekly"]).any()
        return bool(was_below_weekly)
