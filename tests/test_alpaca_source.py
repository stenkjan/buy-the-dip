from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from bot_core.data.base import DataSourceError


def _multi_index_df(symbol: str = "QQQ", n: int = 6) -> pd.DataFrame:
    """Simulate the multi-index (symbol, timestamp) DataFrame BarSet.df returns."""
    timestamps = pd.date_range("2020-01-01", periods=n, freq="MS", tz="UTC")
    index = pd.MultiIndex.from_product([[symbol], timestamps], names=["symbol", "timestamp"])
    return pd.DataFrame(
        {
            "open": range(100, 100 + n),
            "high": range(105, 105 + n),
            "low": range(95, 95 + n),
            "close": range(101, 101 + n),
            "volume": [1_000_000] * n,
            "trade_count": [10_000] * n,
            "vwap": [100.5] * n,
        },
        index=index,
    )


@patch("alpaca.data.historical.StockHistoricalDataClient")
def test_constructor_reads_credentials_from_env(mock_client_cls, monkeypatch):
    monkeypatch.setenv("APCA_API_KEY_ID", "envkey")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "envsecret")
    from bot_core.data.alpaca_source import AlpacaSource

    AlpacaSource()
    mock_client_cls.assert_called_once_with("envkey", "envsecret")


@patch("alpaca.data.historical.StockHistoricalDataClient")
def test_missing_credentials_raises_datasource_error(mock_client_cls, monkeypatch):
    monkeypatch.delenv("APCA_API_KEY_ID", raising=False)
    monkeypatch.delenv("APCA_API_SECRET_KEY", raising=False)
    from bot_core.data.alpaca_source import AlpacaSource

    with pytest.raises(DataSourceError):
        AlpacaSource()


@patch("alpaca.data.historical.StockHistoricalDataClient")
def test_fetch_auto_maps_ndx_to_qqq(mock_client_cls):
    instance = MagicMock()
    bars = SimpleNamespace(df=_multi_index_df(symbol="QQQ"))
    instance.get_stock_bars.return_value = bars
    mock_client_cls.return_value = instance
    from bot_core.data.alpaca_source import AlpacaSource

    src = AlpacaSource(api_key="k", api_secret="s")
    df = src.fetch("^NDX", "1mo")
    # one call, and the request was built with the mapped symbol
    (request,), _ = instance.get_stock_bars.call_args
    assert request.symbol_or_symbols == "QQQ"
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert len(df) == 6
    assert df.index.tz is not None


@patch("alpaca.data.historical.StockHistoricalDataClient")
def test_fetch_interval_mapping_uses_correct_timeframe(mock_client_cls):
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

    instance = MagicMock()
    instance.get_stock_bars.return_value = SimpleNamespace(df=_multi_index_df())
    mock_client_cls.return_value = instance
    from bot_core.data.alpaca_source import AlpacaSource

    src = AlpacaSource(api_key="k", api_secret="s")
    for interval, expected in [
        ("1h", TimeFrame(1, TimeFrameUnit.Hour)),
        ("1d", TimeFrame(1, TimeFrameUnit.Day)),
        ("1wk", TimeFrame(1, TimeFrameUnit.Week)),
        ("1mo", TimeFrame(1, TimeFrameUnit.Month)),
    ]:
        src.fetch("QQQ", interval)
        (request,), _ = instance.get_stock_bars.call_args
        assert request.timeframe.amount_value == expected.amount_value
        assert request.timeframe.unit_value == expected.unit_value


@patch("alpaca.data.historical.StockHistoricalDataClient")
def test_fetch_unsupported_interval_raises(mock_client_cls):
    mock_client_cls.return_value = MagicMock()
    from bot_core.data.alpaca_source import AlpacaSource

    src = AlpacaSource(api_key="k", api_secret="s")
    with pytest.raises(DataSourceError):
        src.fetch("QQQ", "5m")


@patch("alpaca.data.historical.StockHistoricalDataClient")
def test_fetch_empty_response_returns_empty_dataframe(mock_client_cls):
    instance = MagicMock()
    # empty BarSet — its .df accessor returns an empty DataFrame
    instance.get_stock_bars.return_value = SimpleNamespace(df=pd.DataFrame())
    mock_client_cls.return_value = instance
    from bot_core.data.alpaca_source import AlpacaSource

    src = AlpacaSource(api_key="k", api_secret="s")
    df = src.fetch("QQQ", "1d")
    assert df.empty
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]


@patch("alpaca.data.historical.StockHistoricalDataClient")
def test_fetch_multi_symbol_response_is_sliced(mock_client_cls):
    # Even a single-symbol request comes back multi-indexed; ensure we slice.
    instance = MagicMock()
    df = _multi_index_df(symbol="QQQ")
    instance.get_stock_bars.return_value = SimpleNamespace(df=df)
    mock_client_cls.return_value = instance
    from bot_core.data.alpaca_source import AlpacaSource

    src = AlpacaSource(api_key="k", api_secret="s")
    out = src.fetch("^NDX", "1mo")
    # Multi-index has been collapsed to a single DatetimeIndex
    assert not isinstance(out.index, pd.MultiIndex)
    assert (out["close"].values == list(range(101, 107))).all()


@patch("alpaca.data.historical.StockHistoricalDataClient")
def test_sdk_exception_is_wrapped_as_datasource_error(mock_client_cls):
    instance = MagicMock()
    instance.get_stock_bars.side_effect = RuntimeError("boom")
    mock_client_cls.return_value = instance
    from bot_core.data.alpaca_source import AlpacaSource

    src = AlpacaSource(api_key="k", api_secret="s")
    with pytest.raises(DataSourceError):
        src.fetch("QQQ", "1d")


@patch("alpaca.data.historical.StockHistoricalDataClient")
def test_fetch_warns_when_history_is_truncated(mock_client_cls, capsys):
    instance = MagicMock()
    instance.get_stock_bars.return_value = SimpleNamespace(df=_multi_index_df())
    mock_client_cls.return_value = instance
    from bot_core.data.alpaca_source import AlpacaSource

    src = AlpacaSource(api_key="k", api_secret="s")
    # ask for 1996 but mock data starts in 2020
    src.fetch("QQQ", "1mo", start=datetime(1996, 1, 1, tzinfo=UTC))
    err = capsys.readouterr().err
    assert "earliest bar available" in err
