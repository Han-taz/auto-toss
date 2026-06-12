import io
import json

from auto_toss.cli import main
from auto_toss.config import Config


class FakeClient:
    def __init__(self):
        self.calls = []

    def get_prices(self, symbols):
        self.calls.append(("get_prices", symbols))
        return [{"symbol": symbol} for symbol in symbols]

    def get_accounts(self):
        self.calls.append(("get_accounts",))
        return [{"accountSeq": 7}]

    def get_holdings(self, *, account_seq, symbol=None):
        self.calls.append(("get_holdings", account_seq, symbol))
        return {"items": []}

    def create_order(self, *, account_seq, payload):
        self.calls.append(("create_order", account_seq, payload))
        return {"orderId": "order-1", "clientOrderId": payload["clientOrderId"]}


def make_config(*, live=False):
    return Config(
        client_id="client-id",
        client_secret="client-secret",
        live_trading_enabled=live,
    )


def run_cli(argv, *, live=False):
    fake_client = FakeClient()
    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = main(
        argv,
        config_factory=lambda: make_config(live=live),
        client_factory=lambda config: fake_client,
        stdout=stdout,
        stderr=stderr,
    )
    return exit_code, stdout.getvalue(), stderr.getvalue(), fake_client


def test_prices_command_prints_json_result():
    exit_code, stdout, _, fake_client = run_cli(["prices", "005930", "AAPL"])

    assert exit_code == 0
    assert json.loads(stdout) == [{"symbol": "005930"}, {"symbol": "AAPL"}]
    assert fake_client.calls == [("get_prices", ["005930", "AAPL"])]


def test_accounts_command_prints_json_result():
    exit_code, stdout, _, fake_client = run_cli(["accounts"])

    assert exit_code == 0
    assert json.loads(stdout) == [{"accountSeq": 7}]
    assert fake_client.calls == [("get_accounts",)]


def test_holdings_command_passes_account_and_symbol():
    exit_code, stdout, _, fake_client = run_cli(["holdings", "--account", "7", "--symbol", "AAPL"])

    assert exit_code == 0
    assert json.loads(stdout) == {"items": []}
    assert fake_client.calls == [("get_holdings", "7", "AAPL")]


def test_preview_order_prints_payload_and_never_creates_order():
    exit_code, stdout, _, fake_client = run_cli(
        [
            "preview-order",
            "--symbol",
            "005930",
            "--side",
            "BUY",
            "--order-type",
            "LIMIT",
            "--quantity",
            "1",
            "--price",
            "70000",
        ]
    )

    payload = json.loads(stdout)
    assert exit_code == 0
    assert payload["symbol"] == "005930"
    assert payload["orderType"] == "LIMIT"
    assert payload["quantity"] == "1"
    assert payload["price"] == "70000"
    assert fake_client.calls == []


def test_place_order_without_live_flag_exits_nonzero():
    exit_code, _, stderr, fake_client = run_cli(
        [
            "place-order",
            "--account",
            "7",
            "--symbol",
            "005930",
            "--side",
            "BUY",
            "--order-type",
            "LIMIT",
            "--quantity",
            "1",
            "--price",
            "70000",
        ],
        live=True,
    )

    assert exit_code == 2
    assert "Live order placement requires" in stderr
    assert fake_client.calls == []


def test_place_order_live_calls_create_order_when_config_enabled():
    exit_code, stdout, _, fake_client = run_cli(
        [
            "place-order",
            "--live",
            "--account",
            "7",
            "--symbol",
            "005930",
            "--side",
            "BUY",
            "--order-type",
            "LIMIT",
            "--quantity",
            "1",
            "--price",
            "70000",
        ],
        live=True,
    )

    assert exit_code == 0
    assert json.loads(stdout)["orderId"] == "order-1"
    assert fake_client.calls[0][0] == "create_order"
    assert fake_client.calls[0][1] == "7"
    assert fake_client.calls[0][2]["symbol"] == "005930"
