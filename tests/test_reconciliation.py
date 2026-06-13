from auto_toss.reconciliation import reconcile_open_orders


class FakeClient:
    def __init__(self, orders):
        self.orders = orders
        self.calls = []

    def get_orders(self, *, account_seq, status, symbol=None, limit=None, cursor=None):
        self.calls.append((account_seq, status, symbol))
        return self.orders


class FakeAudit:
    def __init__(self, order_ids):
        self.order_ids = order_ids
        self.reports = []

    def live_order_ids(self):
        return self.order_ids

    def record_reconciliation(self, *, account_seq, symbol, report):
        self.reports.append(
            {
                "account_seq": account_seq,
                "symbol": symbol,
                "report": report,
            }
        )
        return len(self.reports)


def test_reconcile_open_orders_classifies_broker_and_local_orders():
    audit = FakeAudit(["local-1", "local-only"])
    client = FakeClient({"orders": [{"orderId": "local-1"}, {"orderId": "broker-only"}]})

    report = reconcile_open_orders(
        client=client,
        audit_store=audit,
        account_seq="7",
        symbol="005930",
    )

    assert report["brokerOpenOrderIds"] == ["broker-only", "local-1"]
    assert report["localSubmittedOrderIds"] == ["local-1", "local-only"]
    assert report["matchedOpenOrderIds"] == ["local-1"]
    assert report["brokerOnlyOpenOrderIds"] == ["broker-only"]
    assert report["localOnlySubmittedOrderIds"] == ["local-only"]
    assert client.calls == [("7", "OPEN", "005930")]
    assert audit.reports[0]["report"] == report


def test_reconcile_open_orders_accepts_list_payload():
    audit = FakeAudit(["order-1"])
    client = FakeClient([{"orderId": "order-1"}])

    report = reconcile_open_orders(
        client=client,
        audit_store=audit,
        account_seq="7",
    )

    assert report["matchedOpenOrderIds"] == ["order-1"]
