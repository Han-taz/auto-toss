from decimal import Decimal

from auto_toss.audit import AuditStore
from auto_toss.runner import StrategyRunner


class FakeTossClient:
    def __init__(self, *, last_price="70000"):
        self.last_price = last_price
        self.calls = []

    def get_prices(self, symbols):
        self.calls.append(("prices", tuple(symbols)))
        return [{"symbol": symbol, "lastPrice": self.last_price} for symbol in symbols]

    def get_stock_warnings(self, symbol):
        self.calls.append(("warnings", symbol))
        return []

    def get_price_limits(self, symbol):
        self.calls.append(("price_limits", symbol))
        return {"lowerLimitPrice": "60000", "upperLimitPrice": "80000"}


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
        return {"fillId": "fill-1", "symbol": symbol}


def write_strategy(
    tmp_path,
    *,
    allowed_symbols,
    intent_symbol,
    trigger="always",
    trigger_price=None,
):
    path = tmp_path / "strategy.toml"
    trigger_block = ""
    if trigger != "always":
        trigger_block = f"""
        [intents.trigger]
        kind = "{trigger}"
        price = "{trigger_price}"
        """
    path.write_text(
        f"""
        [risk]
        max_order_amount = "100000"
        max_daily_notional = "300000"
        max_daily_orders = 5
        allowed_symbols = {allowed_symbols!r}

        [[intents]]
        symbol = "{intent_symbol}"
        side = "BUY"
        currency = "KRW"
        order_type = "LIMIT"
        quantity = "1"
        price = "70000"
        client_order_id = "runner-1"
        {trigger_block}
        """,
        encoding="utf-8",
    )
    return path


def test_runner_records_rejected_intent_without_execution(tmp_path):
    config_path = write_strategy(
        tmp_path,
        allowed_symbols=["AAPL"],
        intent_symbol="005930",
    )
    paper = FakePaperBroker()
    audit = AuditStore(tmp_path / "audit.sqlite3")
    runner = StrategyRunner(
        config_path=config_path,
        mode="paper",
        audit_store=audit,
        toss_client=FakeTossClient(last_price="70000"),
        paper_broker=paper,
        live_allowed=False,
    )

    result = runner.run_once()

    assert result.status == "COMPLETED"
    assert result.executed == 0
    assert result.rejected == 1
    assert paper.calls == []
    assert audit.daily_order_count() == 0
    assert audit.runs()[0]["status"] == "COMPLETED"


def test_runner_executes_paper_intent(tmp_path):
    config_path = write_strategy(
        tmp_path,
        allowed_symbols=["005930"],
        intent_symbol="005930",
    )
    paper = FakePaperBroker()
    audit = AuditStore(tmp_path / "audit.sqlite3")
    runner = StrategyRunner(
        config_path=config_path,
        mode="paper",
        audit_store=audit,
        toss_client=FakeTossClient(last_price="70000"),
        paper_broker=paper,
        live_allowed=False,
    )

    result = runner.run_once()

    assert result.executed == 1
    assert result.rejected == 0
    assert paper.calls == [("005930", "BUY", "KRW", "1", "70000", "runner-1")]
    assert audit.daily_order_count() == 1
    assert audit.daily_notional() == Decimal("70000")


def test_runner_skips_intent_when_trigger_does_not_match(tmp_path):
    config_path = write_strategy(
        tmp_path,
        allowed_symbols=["005930"],
        intent_symbol="005930",
        trigger="last_price_at_or_below",
        trigger_price="69000",
    )
    paper = FakePaperBroker()
    runner = StrategyRunner(
        config_path=config_path,
        mode="paper",
        audit_store=AuditStore(tmp_path / "audit.sqlite3"),
        toss_client=FakeTossClient(last_price="70000"),
        paper_broker=paper,
        live_allowed=False,
    )

    result = runner.run_once()

    assert result.executed == 0
    assert result.rejected == 0
    assert result.skipped == 1
    assert paper.calls == []
