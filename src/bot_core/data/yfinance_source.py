from __future__ import annotations

from datetime import datetime

import pandas as pd


class YFinanceSource:
    """Free-tier source. Intraday history is limited (~60 days for hourly).

    For production, swap in a Polygon/Tiingo source behind the same DataSource Protocol.
    """

    def fetch(
        self,
        symbol: str,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        import yfinance as yf  # local import keeps the framework importable without yfinance

        ticker = yf.Ticker(symbol)
        kwargs: dict[str, object] = {"interval": interval, "auto_adjust": False}
        if start is not None:
            kwargs["start"] = start
        if end is not None:
            kwargs["end"] = end
        if start is None and end is None:
            kwargs["period"] = "max" if interval in {"1d", "1wk", "1mo"} else "60d"

        df = ticker.history(**kwargs)
        if df.empty:
            return df
        df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
        df.index = pd.to_datetime(df.index, utc=True)
        return df
