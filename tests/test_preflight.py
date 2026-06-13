from decimal import Decimal

from auto_toss.preflight import infer_market, run_preflight
from auto_toss.strategy import OrderIntent


class FakeClient:
    def __init__(
        self,
        *,
        warnings=None,
        price_limits=None,
        market_calendar=None,
        buying_power=None,
        sellable_quantity=None,
        orders=None,
    ):
        self.calls = []
        self._warnings = [] if warnings is None else warnings
        self._price_limits = (
            {"lowerLimitPrice": "60000", "upperLimitPrice": "80000"}
            if price_limits is None
            else price_limits
        )
        self._market_calendar = (
            {"sessions": [{"status": "OPEN"}]} if market_calendar is None else market_calendar
        )
        self._buying_power = (
            {"availableAmount": "1000000"} if buying_power is None else buying_power
        )
        self._sellable_quantity = (
            {"sellableQuantity": "10"} if sellable_quantity is None else sellable_quantity
        )
        self._orders = {"orders": []} if orders is None else orders

    def get_stock_warnings(self, symbol):
        self.calls.append(("warnings", symbol))
        return self._warnings

    def get_price_limits(self, symbol):
        self.calls.append(("price_limits", symbol))
        return self._price_limits

    def get_market_calendar(self, market):
        self.calls.append(("calendar", market))
        return self._market_calendar

    def get_buying_power(self, *, account_seq, currency):
        self.calls.append(("buying_power", account_seq, currency))
        return self._buying_power

    def get_sellable_quantity(self, *, account_seq, symbol):
        self.calls.append(("sellable", account_seq, symbol))
        return self._sellable_quantity

    def get_orders(self, *, account_seq, status, symbol=None, limit=None, cursor=None):
        self.calls.append(("orders", account_seq, status, symbol))
        return self._orders


def test_preflight_live_calls_required_toss_checks():
    client = FakeClient()
    intent = OrderIntent(
        symbol="005930",
        side="BUY",
        currency="KRW",
        order_type="LIMIT",
        quantity="1",
        price="70000",
    )

    results = run_preflight(
        client=client,
        intent=intent,
        mode="live",
        account_seq="1",
        notional=Decimal("70000"),
    )

    assert all(result.passed for result in results)
    assert ("warnings", "005930") in client.calls
    assert ("price_limits", "005930") in client.calls
    assert ("calendar", "KR") in client.calls
    assert ("buying_power", "1", "KRW") in client.calls
    assert ("orders", "1", "OPEN", "005930") in client.calls


def test_preflight_paper_skips_live_account_checks():
    client = FakeClient()
    intent = OrderIntent(
        symbol="AAPL",
        side="BUY",
        currency="USD",
        order_type="MARKET",
        quantity="1",
    )

    results = run_preflight(
        client=client,
        intent=intent,
        mode="paper",
        account_seq=None,
        notional=Decimal("200"),
    )

    assert all(result.passed for result in results)
    assert ("warnings", "AAPL") in client.calls
    assert not any(call[0] == "buying_power" for call in client.calls)
    assert not any(call[0] == "orders" for call in client.calls)


def test_preflight_rejects_active_warnings_and_price_outside_limits():
    client = FakeClient(
        warnings=[{"warningType": "INVESTMENT_WARNING"}],
        price_limits={"lowerLimitPrice": "60000", "upperLimitPrice": "80000"},
    )
    intent = OrderIntent(
        symbol="005930",
        side="BUY",
        currency="KRW",
        order_type="LIMIT",
        quantity="1",
        price="90000",
    )

    results = run_preflight(
        client=client,
        intent=intent,
        mode="paper",
        account_seq=None,
        notional=Decimal("90000"),
    )

    rejected = {result.name for result in results if result.status == "REJECT"}
    assert {"stock_warnings", "price_limits"} <= rejected


def test_preflight_rejects_insufficient_buying_power_and_opposite_order():
    client = FakeClient(
        buying_power={"availableAmount": "1000"},
        orders={"orders": [{"symbol": "005930", "side": "SELL"}]},
    )
    intent = OrderIntent(
        symbol="005930",
        side="BUY",
        currency="KRW",
        order_type="LIMIT",
        quantity="1",
        price="70000",
    )

    results = run_preflight(
        client=client,
        intent=intent,
        mode="live",
        account_seq="1",
        notional=Decimal("70000"),
    )

    rejected = {result.name for result in results if result.status == "REJECT"}
    assert {"buying_power", "opposite_open_orders"} <= rejected


def test_preflight_rejects_insufficient_sellable_quantity():
    client = FakeClient(sellable_quantity={"sellableQuantity": "0"})
    intent = OrderIntent(
        symbol="005930",
        side="SELL",
        currency="KRW",
        order_type="LIMIT",
        quantity="1",
        price="70000",
    )

    results = run_preflight(
        client=client,
        intent=intent,
        mode="live",
        account_seq="1",
        notional=Decimal("70000"),
    )

    assert any(
        result.name == "sellable_quantity" and result.status == "REJECT"
        for result in results
    )


def test_infer_market_uses_symbol_shape():
    assert infer_market("005930") == "KR"
    assert infer_market("AAPL") == "US"
