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
    out = df.resample(rule, label="right", closed="right").agg(agg)
    # Empty buckets (overnight/weekend gaps in intraday data) aggregate to a NaN
    # OHLC but volume=sum([])=0, so they survive dropna(how="all") and poison
    # downstream indicators (RSI/EMA go all-NaN). Drop any bucket with no close.
    subset = [cols["close"]] if "close" in cols else None
    return out.dropna(subset=subset) if subset else out.dropna(how="all")
