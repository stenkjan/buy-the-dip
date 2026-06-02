"""Alpaca historical OHLCV source implementing the DataSource Protocol.

Uses alpaca-py's StockHistoricalDataClient. The free IEX feed has a ~15min
realtime delay and limited history depth (roughly 2016+ for most ETFs);
Algo Trader Plus / SIP gets full history. We pass through whatever the
endpoint returns and warn to stderr if the earliest bar is later than the
requested start.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .base import DataSourceError
from .symbols import to_alpaca_symbol

_COLUMNS = ["open", "high", "low", "close", "volume"]


class AlpacaSource:
    """OHLCV from Alpaca Market Data. Lazy-imports the SDK on construction."""

    name = "alpaca"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_secret: str | None = None,
        mapping_path: Path | None = None,
    ) -> None:
        # Local import so the package stays importable without alpaca-py.
        from alpaca.data.historical import StockHistoricalDataClient

        key = api_key or os.getenv("APCA_API_KEY_ID")
        secret = api_secret or os.getenv("APCA_API_SECRET_KEY")
        if not key or not secret:
            raise DataSourceError(
                "Alpaca credentials missing: set APCA_API_KEY_ID and APCA_API_SECRET_KEY"
            )
        try:
            self._client = StockHistoricalDataClient(key, secret)
        except Exception as exc:
            raise DataSourceError(f"failed to construct StockHistoricalDataClient: {exc}") from exc
        self._mapping_path = mapping_path

    def _timeframe(self, interval: str) -> Any:
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

        match interval:
            case "1h":
                return TimeFrame(1, TimeFrameUnit.Hour)
            case "1d":
                return TimeFrame(1, TimeFrameUnit.Day)
            case "1wk":
                return TimeFrame(1, TimeFrameUnit.Week)
            case "1mo":
                return TimeFrame(1, TimeFrameUnit.Month)
            case _:
                raise DataSourceError(
                    f"unsupported interval {interval!r}; use 1h, 1d, 1wk, or 1mo"
                )

    def fetch(
        self,
        symbol: str,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        from alpaca.data.requests import StockBarsRequest

        mapped = to_alpaca_symbol(symbol, self._mapping_path)
        tf = self._timeframe(interval)

        req_kwargs: dict[str, Any] = {"symbol_or_symbols": mapped, "timeframe": tf}
        if start is not None:
            req_kwargs["start"] = start
        if end is not None:
            req_kwargs["end"] = end
        try:
            request = StockBarsRequest(**req_kwargs)
            bars = self._client.get_stock_bars(request)
        except Exception as exc:
            raise DataSourceError(f"Alpaca get_stock_bars failed: {exc}") from exc

        df = self._to_dataframe(bars, mapped)
        if df.empty:
            return df

        if start is not None:
            requested_start = pd.Timestamp(start)
            if requested_start.tzinfo is None:
                requested_start = requested_start.tz_localize("UTC")
            else:
                requested_start = requested_start.tz_convert("UTC")
            earliest = df.index[0]
            # Tolerate ~1 trading day of slack — Alpaca aligns to session opens.
            if earliest - requested_start > pd.Timedelta(days=2):
                print(
                    f"warning: requested start {requested_start.date()} but earliest bar "
                    f"available is {earliest.date()} — proceeding with shorter history",
                    file=sys.stderr,
                )
        return df

    @staticmethod
    def _to_dataframe(bars: Any, symbol: str) -> pd.DataFrame:
        # SDK returns a BarSet with `.df` (multi-index symbol, timestamp) or a
        # plain dict when raw_data=True. Handle both defensively.
        raw = getattr(bars, "df", None)
        if raw is None:
            data = getattr(bars, "data", None) or bars
            if isinstance(data, dict):
                rows = data.get(symbol, [])
                if not rows:
                    return pd.DataFrame(columns=_COLUMNS)
                df = pd.DataFrame(rows)
            else:
                return pd.DataFrame(columns=_COLUMNS)
        else:
            df = raw

        if df is None or df.empty:
            return pd.DataFrame(columns=_COLUMNS)

        # Multi-index (symbol, timestamp) → slice to the requested symbol.
        if isinstance(df.index, pd.MultiIndex):
            level_names = df.index.names
            if "symbol" in level_names and symbol in df.index.get_level_values("symbol"):
                df = df.xs(symbol, level="symbol")
            else:
                # Single symbol — just drop the first level regardless of name.
                df = df.droplevel(0)

        # Normalize column case for safety.
        df = df.rename(columns=str.lower)
        missing = [c for c in _COLUMNS if c not in df.columns]
        if missing:
            raise DataSourceError(
                f"Alpaca response missing expected columns: {missing} (got {list(df.columns)})"
            )
        df = df[_COLUMNS].copy()
        df.index = pd.to_datetime(df.index, utc=True)
        df = df.sort_index()
        return df
