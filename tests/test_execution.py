from decimal import Decimal

import pytest

from auto_toss.execution import execute_intent
from auto_toss.orders import LiveTradingNotEnabled
from auto_toss.strategy import OrderIntent


class FakePaperBroker:
    def __init__(self):
        self.calls = []

    def execute_order(
        self,
        *,
        symbol,
        side,
        currency,
        quantity,
        fill_price,
        client_order_id=None,
    ):
        self.calls.append((symbol, side, currency, quantity, fill_price, client_order_id))
        return {"fillId": "fill-1", "symbol": symbol, "side": side}


class FakeLiveClient:
    def __init__(self):
        self.calls = []

    def create_order(self, *, account_seq, payload):
        self.calls.append((account_seq, payload))
        return {"orderId": "order-1", "clientOrderId": payload["clientOrderId"]}


def test_paper_execution_uses_paper_broker_and_not_live_client():
    broker = FakePaperBroker()
    live_client = FakeLiveClient()
    intent = OrderIntent(
        symbol="005930",
        side="BUY",
        currency="KRW",
        order_type="LIMIT",
        quantity="1",
        price="70000",
        client_order_id="paper-1",
    )

    result = execute_intent(
        intent=intent,
        mode="paper",
        paper_broker=broker,
        live_client=live_client,
        account_seq=None,
        live_allowed=False,
        fill_price=Decimal("70000"),
    )

    assert result.status == "FILLED"
    assert broker.calls == [("005930", "BUY", "KRW", "1", "70000", "paper-1")]
    assert live_client.calls == []


def test_paper_market_execution_uses_supplied_fill_price():
    broker = FakePaperBroker()
    intent = OrderIntent(
        symbol="AAPL",
        side="BUY",
        currency="USD",
        order_type="MARKET",
        quantity="1",
    )

    result = execute_intent(
        intent=intent,
        mode="paper",
        paper_broker=broker,
        live_client=FakeLiveClient(),
        account_seq=None,
        live_allowed=False,
        fill_price=Decimal("200.50"),
    )

    assert result.status == "FILLED"
    assert broker.calls[0][4] == "200.5"


def test_live_execution_requires_existing_live_gate():
    intent = OrderIntent(
        symbol="005930",
        side="BUY",
        currency="KRW",
        order_type="LIMIT",
        quantity="1",
        price="70000",
    )

    with pytest.raises(LiveTradingNotEnabled):
        execute_intent(
            intent=intent,
            mode="live",
            paper_broker=FakePaperBroker(),
            live_client=FakeLiveClient(),
            account_seq="1",
            live_allowed=False,
            fill_price=Decimal("70000"),
        )


def test_live_execution_creates_toss_order_when_allowed():
    live_client = FakeLiveClient()
    intent = OrderIntent(
        symbol="005930",
        side="BUY",
        currency="KRW",
        order_type="LIMIT",
        quantity="1",
        price="70000",
        client_order_id="live-1",
    )

    result = execute_intent(
        intent=intent,
        mode="live",
        paper_broker=FakePaperBroker(),
        live_client=live_client,
        account_seq="1",
        live_allowed=True,
        fill_price=Decimal("70000"),
    )

    assert result.status == "SUBMITTED"
    assert live_client.calls == [
        (
            "1",
            {
                "clientOrderId": "live-1",
                "symbol": "005930",
                "side": "BUY",
                "orderType": "LIMIT",
                "quantity": "1",
                "price": "70000",
            },
        )
    ]
