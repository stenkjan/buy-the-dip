from __future__ import annotations

import os
from datetime import datetime
from typing import Any

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

# Map Alpaca's status vocabulary onto our smaller normalised set.
_STATUS_MAP: dict[str, OrderStatus] = {
    "new": "accepted",
    "accepted": "accepted",
    "pending_new": "pending",
    "pending_review": "pending",
    "accepted_for_bidding": "accepted",
    "partially_filled": "partially_filled",
    "filled": "filled",
    "canceled": "cancelled",
    "pending_cancel": "pending",
    "expired": "expired",
    "rejected": "rejected",
    "suspended": "rejected",
    "held": "pending",
    "done_for_day": "expired",
    "replaced": "cancelled",
    "pending_replace": "pending",
    "stopped": "cancelled",
    "calculated": "pending",
}


class AlpacaBroker:
    """Concrete Broker implementing the protocol against Alpaca's REST API.

    Imports `alpaca-py` lazily so the framework stays importable when the
    optional SDK isn't installed (mirrors YFinanceSource).
    """

    name = "alpaca"

    def __init__(
        self,
        *,
        mode: Mode = "paper",
        api_key: str | None = None,
        api_secret: str | None = None,
    ) -> None:
        from alpaca.trading.client import TradingClient  # local import on purpose

        self.mode: Mode = mode
        key = api_key or os.getenv("APCA_API_KEY_ID")
        secret = api_secret or os.getenv("APCA_API_SECRET_KEY")
        if not key or not secret:
            raise BrokerError(
                "Alpaca credentials missing: set APCA_API_KEY_ID and APCA_API_SECRET_KEY"
            )
        try:
            self._client = TradingClient(key, secret, paper=(mode == "paper"))
        except Exception as exc:  # wrap any SDK init failure
            raise BrokerError(f"failed to construct Alpaca TradingClient: {exc}") from exc

    # ----- queries -----

    def get_account(self) -> Account:
        try:
            a = self._client.get_account()
        except Exception as exc:
            raise BrokerError(f"get_account failed: {exc}") from exc
        return Account(
            cash=float(a.cash),
            buying_power=float(a.buying_power),
            equity=float(a.equity),
            currency=str(getattr(a, "currency", "USD")),
        )

    def get_positions(self) -> list[BrokerPosition]:
        try:
            positions = self._client.get_all_positions()
        except Exception as exc:
            raise BrokerError(f"get_positions failed: {exc}") from exc
        return [
            BrokerPosition(
                symbol=str(p.symbol),
                qty=float(p.qty),
                avg_entry_price=float(p.avg_entry_price),
                market_value=float(p.market_value),
                unrealized_pl=float(p.unrealized_pl),
            )
            for p in positions
        ]

    def get_order(self, order_id: str) -> BrokerOrder:
        try:
            o = self._client.get_order_by_id(order_id)
        except Exception as exc:
            raise BrokerError(f"get_order({order_id}) failed: {exc}") from exc
        return self._to_broker_order(o)

    # ----- mutations -----

    def place_market_order(self, symbol: str, side: Side, qty: float) -> BrokerOrder:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        req = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        try:
            order = self._client.submit_order(order_data=req)
        except Exception as exc:
            raise BrokerError(f"submit market order failed: {exc}") from exc
        return self._to_broker_order(order)

    def place_limit_order(
        self,
        symbol: str,
        side: Side,
        qty: float,
        limit_price: float,
        time_in_force: str = "day",
    ) -> BrokerOrder:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest

        tif = {
            "day": TimeInForce.DAY,
            "gtc": TimeInForce.GTC,
            "opg": TimeInForce.OPG,
            "cls": TimeInForce.CLS,
            "ioc": TimeInForce.IOC,
            "fok": TimeInForce.FOK,
        }.get(time_in_force.lower(), TimeInForce.DAY)
        req = LimitOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
            time_in_force=tif,
            limit_price=limit_price,
        )
        try:
            order = self._client.submit_order(order_data=req)
        except Exception as exc:
            raise BrokerError(f"submit limit order failed: {exc}") from exc
        return self._to_broker_order(order)

    def cancel_order(self, order_id: str) -> None:
        try:
            self._client.cancel_order_by_id(order_id)
        except Exception as exc:
            raise BrokerError(f"cancel_order({order_id}) failed: {exc}") from exc

    # ----- mapping -----

    @staticmethod
    def _to_broker_order(o: Any) -> BrokerOrder:
        status_raw = str(getattr(o, "status", "pending")).lower().split(".")[-1]
        side_raw = str(getattr(o, "side", "buy")).lower().split(".")[-1]
        side: Side = "sell" if side_raw == "sell" else "buy"
        limit_price = getattr(o, "limit_price", None)
        filled_avg = getattr(o, "filled_avg_price", None)
        submitted = getattr(o, "submitted_at", None)
        return BrokerOrder(
            id=str(o.id),
            symbol=str(o.symbol),
            side=side,
            qty=float(o.qty),
            status=_STATUS_MAP.get(status_raw, "pending"),
            limit_price=float(limit_price) if limit_price is not None else None,
            filled_qty=float(getattr(o, "filled_qty", 0) or 0),
            filled_avg_price=float(filled_avg) if filled_avg is not None else None,
            submitted_at=submitted if isinstance(submitted, datetime) else None,
        )


# Static structural check at import-time. Cheap; prevents accidental drift.
_: type[Broker] = AlpacaBroker
