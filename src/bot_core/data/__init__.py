from .base import DataSource, DataSourceError
from .symbols import to_alpaca_symbol
from .yfinance_source import YFinanceSource


def __getattr__(name: str):  # pragma: no cover - thin re-export shim
    # Lazy re-export of AlpacaSource so importing bot_core.data doesn't pull
    # in alpaca-py when it's not installed.
    if name == "AlpacaSource":
        from .alpaca_source import AlpacaSource

        return AlpacaSource
    raise AttributeError(name)


__all__ = [
    "AlpacaSource",
    "DataSource",
    "DataSourceError",
    "YFinanceSource",
    "to_alpaca_symbol",
]
