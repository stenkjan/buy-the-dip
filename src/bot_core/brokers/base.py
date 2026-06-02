from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

Mode = Literal["paper", "live"]
Side = Literal["buy", "sell"]
OrderStatus = Literal[
    "pending", "accepted", "filled", "partially_filled", "cancelled", "rejected", "expired"
]


class BrokerError(RuntimeError):
    """Wraps any broker-specific exception so callers can catch a single type."""


@dataclass(frozen=True)
class Account:
    cash: float
    buying_power: float
    equity: float
    currency: str


@dataclass(frozen=True)
class BrokerPosition:
    symbol: str
    qty: float
    avg_entry_price: float
    market_value: float
    unrealized_pl: float


@dataclass(frozen=True)
class BrokerOrder:
    id: str
    symbol: str
    side: Side
    qty: float
    status: OrderStatus
    limit_price: float | None
    filled_qty: float
    filled_avg_price: float | None
    submitted_at: datetime | None


@runtime_checkable
class Broker(Protocol):
    name: str
    mode: Mode

    def get_account(self) -> Account: ...

    def get_positions(self) -> list[BrokerPosition]: ...

    def place_market_order(self, symbol: str, side: Side, qty: float) -> BrokerOrder: ...

    def place_limit_order(
        self,
        symbol: str,
        side: Side,
        qty: float,
        limit_price: float,
        time_in_force: str = "day",
    ) -> BrokerOrder: ...

    def get_order(self, order_id: str) -> BrokerOrder: ...

    def cancel_order(self, order_id: str) -> None: ...
