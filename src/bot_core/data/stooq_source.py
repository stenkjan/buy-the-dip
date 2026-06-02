"""Stooq OHLC source — free daily history, no API key, no cookies.

A single host (`stooq.com`) returns a plain CSV with the full daily history of
an index, which makes it far friendlier to a sandbox network allowlist than the
multi-host cookie/crumb dance yfinance performs against Yahoo. Intended for the
backtest / DCA paths, which only need daily closes.

Symbols are given Yahoo-style (`^NDX`, `^GSPC`) and mapped to Stooq tickers.
"""

from __future__ import annotations

from datetime import datetime
from io import StringIO

import pandas as pd

# Yahoo-style symbol -> Stooq ticker. Stooq uses ^spx for the S&P 500 index.
_SYMBOL_MAP = {
    "^GSPC": "^spx",
    "^SPX": "^spx",
    "^NDX": "^ndx",
    "^IXIC": "^ndq",
    "^DJI": "^dji",
}


def to_stooq_symbol(symbol: str) -> str:
    return _SYMBOL_MAP.get(symbol.upper(), symbol.lower())


def parse_stooq_csv(text: str) -> pd.DataFrame:
    """Parse a Stooq daily CSV (Date,Open,High,Low,Close,Volume) into the
    framework's OHLCV shape: UTC DatetimeIndex, lowercase columns.
    """
    try:
        df = pd.read_csv(StringIO(text))
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    if df.empty or "Date" not in df.columns or "Close" not in df.columns:
        return pd.DataFrame()
    df.columns = [c.lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.set_index("date").sort_index()
    if "volume" not in df.columns:
        df["volume"] = 0.0
    return df[["open", "high", "low", "close", "volume"]].astype(float)


class StooqSource:
    """Daily OHLC from stooq.com. Only the `1d` interval is supported."""

    BASE_URL = "https://stooq.com/q/d/l/"

    def fetch(
        self,
        symbol: str,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        import httpx  # local import keeps the framework importable without httpx

        if interval != "1d":
            raise ValueError("StooqSource only supports the '1d' interval")

        params = {"s": to_stooq_symbol(symbol), "i": "d"}
        resp = httpx.get(self.BASE_URL, params=params, timeout=30.0, follow_redirects=True)
        resp.raise_for_status()
        df = parse_stooq_csv(resp.text)
        if df.empty:
            return df
        if start is not None:
            df = df.loc[df.index >= pd.Timestamp(start, tz="UTC")]
        if end is not None:
            df = df.loc[df.index <= pd.Timestamp(end, tz="UTC")]
        return df
