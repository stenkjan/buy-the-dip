from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from bot_core.brokers import AlpacaBroker, Broker, BrokerError


def _fake_account(**overrides):
    base = dict(cash="1000.50", buying_power="2000", equity="5000", currency="USD")
    base.update(overrides)
    return SimpleNamespace(**base)


def _fake_alpaca_order(**overrides):
    base = dict(
        id="ord-1",
        symbol="AAPL",
        side="OrderSide.BUY",
        qty="1",
        status="OrderStatus.ACCEPTED",
        limit_price=None,
        filled_qty="0",
        filled_avg_price=None,
        submitted_at=datetime(2025, 5, 1, 12, 0, tzinfo=UTC),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@patch("alpaca.trading.client.TradingClient")
def test_paper_mode_constructs_client_with_paper_true(mock_client):
    AlpacaBroker(mode="paper", api_key="k", api_secret="s")
    mock_client.assert_called_once_with("k", "s", paper=True)


@patch("alpaca.trading.client.TradingClient")
def test_live_mode_constructs_client_with_paper_false(mock_client):
    AlpacaBroker(mode="live", api_key="k", api_secret="s")
    mock_client.assert_called_once_with("k", "s", paper=False)


def test_missing_credentials_raises_brokererror(monkeypatch):
    monkeypatch.delenv("APCA_API_KEY_ID", raising=False)
    monkeypatch.delenv("APCA_API_SECRET_KEY", raising=False)
    with pytest.raises(BrokerError):
        AlpacaBroker(mode="paper")


@patch("alpaca.trading.client.TradingClient")
def test_get_account_maps_alpaca_fields(mock_client):
    instance = MagicMock()
    instance.get_account.return_value = _fake_account()
    mock_client.return_value = instance
    broker = AlpacaBroker(mode="paper", api_key="k", api_secret="s")
    acc = broker.get_account()
    assert acc.cash == 1000.5
    assert acc.buying_power == 2000.0
    assert acc.equity == 5000.0
    assert acc.currency == "USD"


@patch("alpaca.trading.client.TradingClient")
def test_get_positions_maps_each_position(mock_client):
    instance = MagicMock()
    instance.get_all_positions.return_value = [
        SimpleNamespace(
            symbol="AAPL", qty="3", avg_entry_price="100", market_value="330", unrealized_pl="30"
        )
    ]
    mock_client.return_value = instance
    broker = AlpacaBroker(mode="paper", api_key="k", api_secret="s")
    [p] = broker.get_positions()
    assert p.symbol == "AAPL"
    assert p.qty == 3.0
    assert p.unrealized_pl == 30.0


@patch("alpaca.trading.client.TradingClient")
def test_place_market_order_maps_side(mock_client):
    instance = MagicMock()
    instance.submit_order.return_value = _fake_alpaca_order()
    mock_client.return_value = instance
    broker = AlpacaBroker(mode="paper", api_key="k", api_secret="s")
    order = broker.place_market_order("AAPL", "buy", 1)
    assert order.id == "ord-1"
    assert order.symbol == "AAPL"
    assert order.side == "buy"
    assert order.status == "accepted"
    instance.submit_order.assert_called_once()


@patch("alpaca.trading.client.TradingClient")
def test_place_limit_order_passes_limit_price(mock_client):
    instance = MagicMock()
    instance.submit_order.return_value = _fake_alpaca_order(limit_price="99.5")
    mock_client.return_value = instance
    broker = AlpacaBroker(mode="paper", api_key="k", api_secret="s")
    order = broker.place_limit_order("AAPL", "buy", 1, 99.5)
    assert order.limit_price == 99.5
    _args, kwargs = instance.submit_order.call_args
    sent_req = kwargs["order_data"]
    assert float(sent_req.limit_price) == 99.5


@patch("alpaca.trading.client.TradingClient")
def test_cancel_order_passes_id(mock_client):
    instance = MagicMock()
    mock_client.return_value = instance
    broker = AlpacaBroker(mode="paper", api_key="k", api_secret="s")
    broker.cancel_order("ord-1")
    instance.cancel_order_by_id.assert_called_once_with("ord-1")


@patch("alpaca.trading.client.TradingClient")
def test_alpaca_broker_satisfies_protocol(mock_client):
    broker = AlpacaBroker(mode="paper", api_key="k", api_secret="s")
    assert isinstance(broker, Broker)


@patch("alpaca.trading.client.TradingClient")
def test_sdk_error_is_wrapped_as_broker_error(mock_client):
    instance = MagicMock()
    instance.get_account.side_effect = RuntimeError("boom")
    mock_client.return_value = instance
    broker = AlpacaBroker(mode="paper", api_key="k", api_secret="s")
    with pytest.raises(BrokerError):
        broker.get_account()
