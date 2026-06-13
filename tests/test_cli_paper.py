import io
import json

from auto_toss.cli import main
from auto_toss.config import Config


class FakePaperBroker:
    def __init__(self):
        self.calls = []

    def initialize(self, *, reset=False, krw_cash="10000000", usd_cash="10000"):
        self.calls.append(("initialize", reset, krw_cash, usd_cash))
        return {"cash": {"KRW": krw_cash, "USD": usd_cash}, "positions": []}

    def execute_order(self, *, symbol, side, currency, quantity, fill_price, client_order_id=None):
        self.calls.append(
            ("execute_order", symbol, side, currency, quantity, fill_price, client_order_id)
        )
        return {
            "fillId": "fill-1",
            "symbol": symbol,
            "side": side,
            "currency": currency,
            "quantity": quantity,
            "fillPrice": fill_price,
            "clientOrderId": client_order_id,
        }

    def portfolio(self, *, mark_prices=None):
        self.calls.append(("portfolio", mark_prices or {}))
        return {"cash": {"KRW": "10000000", "USD": "10000"}, "positions": []}

    def ledger(self, *, limit=50):
        self.calls.append(("ledger", limit))
        return [{"fillId": "fill-1"}]


def make_config():
    return Config(client_id="client-id", client_secret="client-secret")


def run_cli(argv):
    broker = FakePaperBroker()
    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = main(
        argv,
        config_factory=make_config,
        paper_broker_factory=lambda db_path=None: broker,
        stdout=stdout,
        stderr=stderr,
    )
    return exit_code, stdout.getvalue(), stderr.getvalue(), broker


def test_paper_init_uses_default_cash_and_reset_flag():
    exit_code, stdout, _, broker = run_cli(["paper-init", "--reset"])

    assert exit_code == 0
    assert json.loads(stdout)["cash"] == {"KRW": "10000000", "USD": "10000"}
    assert broker.calls == [("initialize", True, "10000000", "10000")]


def test_paper_init_accepts_custom_cash():
    exit_code, _, _, broker = run_cli(
        ["paper-init", "--krw-cash", "500000", "--usd-cash", "250"]
    )

    assert exit_code == 0
    assert broker.calls == [("initialize", False, "500000", "250")]


def test_paper_order_executes_fill():
    exit_code, stdout, _, broker = run_cli(
        [
            "paper-order",
            "--symbol",
            "005930",
            "--side",
            "BUY",
            "--currency",
            "KRW",
            "--quantity",
            "1",
            "--fill-price",
            "70000",
            "--client-order-id",
            "paper-1",
        ]
    )

    assert exit_code == 0
    assert json.loads(stdout)["fillId"] == "fill-1"
    assert broker.calls == [
        ("execute_order", "005930", "BUY", "KRW", "1", "70000", "paper-1")
    ]


def test_paper_portfolio_accepts_mark_prices():
    exit_code, stdout, _, broker = run_cli(
        ["paper-portfolio", "--mark-price", "005930=71000", "--mark-price", "AAPL=200"]
    )

    assert exit_code == 0
    assert json.loads(stdout)["positions"] == []
    assert broker.calls == [("portfolio", {"005930": "71000", "AAPL": "200"})]


def test_paper_ledger_uses_limit():
    exit_code, stdout, _, broker = run_cli(["paper-ledger", "--limit", "10"])

    assert exit_code == 0
    assert json.loads(stdout) == [{"fillId": "fill-1"}]
    assert broker.calls == [("ledger", 10)]
