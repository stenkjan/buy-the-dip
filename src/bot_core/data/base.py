from __future__ import annotations

from datetime import datetime
from typing import Protocol

import pandas as pd


class DataSource(Protocol):
    """Pluggable OHLCV provider. Implementations: yfinance, polygon, tiingo, csv."""

    def fetch(
        self,
        symbol: str,
        interval: str,           # "1h", "1d", "1wk"
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """Return DataFrame indexed by UTC DatetimeIndex with columns open/high/low/close/volume."""
        ...
