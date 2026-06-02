"""Broker abstraction. Production-bound implementations live alongside.

The framework deals only in `Broker`, `Account`, `BrokerPosition`, `BrokerOrder`
— the Alpaca adapter is the first concrete implementation and is imported
lazily, so this package stays importable without `alpaca-py` installed.
"""

from .alpaca import AlpacaBroker
from .base import (
    Account,
    Broker,
    BrokerError,
    BrokerOrder,
    BrokerPosition,
    Mode,
    OrderStatus,
    Side,
)

__all__ = [
    "Account",
    "AlpacaBroker",
    "Broker",
    "BrokerError",
    "BrokerOrder",
    "BrokerPosition",
    "Mode",
    "OrderStatus",
    "Side",
]
