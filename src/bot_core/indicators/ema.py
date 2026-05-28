from __future__ import annotations

import pandas as pd


def ema(close: pd.Series, length: int = 200) -> pd.Series:
    return close.ewm(span=length, adjust=False, min_periods=length).mean()
