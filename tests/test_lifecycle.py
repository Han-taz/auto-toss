import pytest

from auto_toss.lifecycle import (
    OrderLifecycleService,
    OrderModifyRequest,
    build_modify_payload,
)
from auto_toss.orders import OrderValidationError


class FakeClient:
    def __init__(self):
        self.calls = []

    def cancel_order(self, *, account_seq, order_id):
        self.calls.append(("cancel_order", account_seq, order_id))
        return {"orderId": "cancel-1"}

    def modify_order(self, *, account_seq, order_id, payload):
        self.calls.append(("modify_order", account_seq, order_id, payload))
        return {"orderId": "modify-1"}


class FakeAudit:
    def __init__(self):
        self.events = []

    def record_order_event(self, **kwargs):
        self.events.append(kwargs)
        return len(self.events)


def test_build_modify_payload_enforces_kr_quantity_and_limit_price():
    payload = build_modify_payload(
        OrderModifyRequest(
            symbol="005930",
            order_type="LIMIT",
            quantity="1",
            price="70000",
        )
    )

    assert payload == {"orderType": "LIMIT", "quantity": "1", "price": "70000"}


def test_build_modify_payload_rejects_kr_without_quantity():
    with pytest.raises(OrderValidationError, match="KR modify requires quantity"):
        build_modify_payload(
            OrderModifyRequest(symbol="005930", order_type="LIMIT", price="70000")
        )


def test_build_modify_payload_rejects_us_quantity():
    with pytest.raises(OrderValidationError, match="US modify does not support quantity"):
        build_modify_payload(
            OrderModifyRequest(
                symbol="AAPL",
                order_type="LIMIT",
                quantity="1",
                price="200",
            )
        )


def test_build_modify_payload_rejects_market_with_price():
    with pytest.raises(OrderValidationError, match="MARKET modify must not include price"):
        build_modify_payload(
            OrderModifyRequest(
                symbol="005930",
                order_type="MARKET",
                quantity="1",
                price="70000",
            )
        )


def test_lifecycle_service_records_cancel_event():
    audit = FakeAudit()
    service = OrderLifecycleService(client=FakeClient(), audit_store=audit)

    result = service.cancel_order(account_seq="7", order_id="order-1")

    assert result == {"orderId": "cancel-1"}
    assert audit.events[0]["event_type"] == "CANCEL"
    assert audit.events[0]["order_id"] == "cancel-1"
    assert audit.events[0]["source_order_id"] == "order-1"


def test_lifecycle_service_records_modify_event():
    audit = FakeAudit()
    service = OrderLifecycleService(client=FakeClient(), audit_store=audit)
    request = OrderModifyRequest(
        symbol="005930",
        order_type="LIMIT",
        quantity="1",
        price="70000",
        confirm_high_value_order=True,
    )

    result = service.modify_order(account_seq="7", order_id="order-1", request=request)

    assert result == {"orderId": "modify-1"}
    assert audit.events[0]["event_type"] == "MODIFY"
    assert audit.events[0]["payload"] == {
        "orderType": "LIMIT",
        "quantity": "1",
        "price": "70000",
        "confirmHighValueOrder": True,
    }
