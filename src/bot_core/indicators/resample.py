from __future__ import annotations

import pandas as pd

_OHLC_AGG: dict[str, str] = {
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "volume": "sum",
}


def resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    # `df` must have a DatetimeIndex and lower-case OHLCV columns.
    # `rule` examples: "12h", "1D", "1W".
    cols = {c.lower(): c for c in df.columns}
    agg = {cols[k]: v for k, v in _OHLC_AGG.items() if k in cols}
    return df.resample(rule, label="right", closed="right").agg(agg).dropna(how="all")
