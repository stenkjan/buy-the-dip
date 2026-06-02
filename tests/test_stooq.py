from __future__ import annotations

import pandas as pd

from bot_core.data.stooq_source import parse_stooq_csv, to_stooq_symbol


def test_symbol_mapping():
    assert to_stooq_symbol("^GSPC") == "^spx"
    assert to_stooq_symbol("^NDX") == "^ndx"
    assert to_stooq_symbol("^gspc") == "^spx"
    # Unknown symbols fall through, lowercased.
    assert to_stooq_symbol("AAPL") == "aapl"


def test_parse_stooq_csv_shape():
    csv = (
        "Date,Open,High,Low,Close,Volume\n"
        "2000-01-03,3790.55,3850.00,3700.00,3790.55,0\n"
        "2000-01-04,3780.00,3800.00,3650.00,3690.00,0\n"
    )
    df = parse_stooq_csv(csv)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert isinstance(df.index, pd.DatetimeIndex)
    assert str(df.index.tz) == "UTC"
    assert df["close"].iloc[0] == 3790.55
    assert len(df) == 2


def test_parse_stooq_csv_handles_no_data():
    # Stooq returns a plain "No data" line when a symbol/range is empty.
    assert parse_stooq_csv("No data\n").empty
    assert parse_stooq_csv("").empty
