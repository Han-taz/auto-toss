import io
import json

import pytest

from auto_toss.cli import main
from auto_toss.config import Config
from auto_toss.lifecycle import OrderModifyRequest


class FakeRunResult:
    def to_dict(self):
        return {
            "runId": 1,
            "status": "COMPLETED",
            "executed": 0,
            "rejected": 0,
            "skipped": 0,
        }


class FakeRunner:
    def __init__(self):
        self.calls = []

    def run_once(self):
        self.calls.append(("run_once",))
        return FakeRunResult()


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

    def get_orders(self, *, account_seq, status, symbol=None, limit=None, cursor=None):
        self.calls.append(("get_orders", account_seq, status, symbol, limit, cursor))
        return {"orders": [{"orderId": "order-1"}]}

    def get_order(self, *, account_seq, order_id):
        self.calls.append(("get_order", account_seq, order_id))
        return {"orderId": order_id}

    def create_order(self, *, account_seq, payload):
        self.calls.append(("create_order", account_seq, payload))
        return {"orderId": "order-1", "clientOrderId": payload["clientOrderId"]}


class FakeLifecycleService:
    def __init__(self):
        self.calls = []

    def cancel_order(self, *, account_seq, order_id):
        self.calls.append(("cancel_order", account_seq, order_id))
        return {"orderId": "cancel-1"}

    def modify_order(self, *, account_seq, order_id, request):
        self.calls.append(("modify_order", account_seq, order_id, request))
        return {"orderId": "modify-1"}


def make_config(*, live=False):
    return Config(
        client_id="client-id",
        client_secret="client-secret",
        live_trading_enabled=live,
    )


def run_cli(
    argv,
    *,
    live=False,
    sleep=None,
    runner_factory=None,
    lifecycle_service_factory=None,
    reconciliation_factory=None,
):
    fake_client = FakeClient()
    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = main(
        argv,
        config_factory=lambda: make_config(live=live),
        client_factory=lambda config: fake_client,
        runner_factory=runner_factory,
        lifecycle_service_factory=lifecycle_service_factory,
        reconciliation_factory=reconciliation_factory,
        sleep=sleep,
        stdout=stdout,
        stderr=stderr,
    )
    return exit_code, stdout.getvalue(), stderr.getvalue(), fake_client


def test_prices_command_prints_json_result():
    exit_code, stdout, _, fake_client = run_cli(["prices", "005930", "AAPL"])

    assert exit_code == 0
    assert json.loads(stdout) == [{"symbol": "005930"}, {"symbol": "AAPL"}]
    assert fake_client.calls == [("get_prices", ["005930", "AAPL"])]


def test_watch_prices_streams_json_snapshots_for_each_iteration():
    sleeps = []

    exit_code, stdout, _, fake_client = run_cli(
        ["watch-prices", "005930", "AAPL", "--iterations", "2", "--interval", "1.25"],
        sleep=sleeps.append,
    )

    assert exit_code == 0
    assert [json.loads(line) for line in stdout.splitlines()] == [
        {
            "sequence": 1,
            "prices": [{"symbol": "005930"}, {"symbol": "AAPL"}],
        },
        {
            "sequence": 2,
            "prices": [{"symbol": "005930"}, {"symbol": "AAPL"}],
        },
    ]
    assert fake_client.calls == [
        ("get_prices", ["005930", "AAPL"]),
        ("get_prices", ["005930", "AAPL"]),
    ]
    assert sleeps == [1.25]


def test_watch_prices_returns_130_when_interrupted_between_polls():
    def interrupt(_seconds):
        raise KeyboardInterrupt

    exit_code, stdout, _, fake_client = run_cli(
        ["watch-prices", "005930", "--interval", "1"],
        sleep=interrupt,
    )

    assert exit_code == 130
    assert json.loads(stdout) == {
        "sequence": 1,
        "prices": [{"symbol": "005930"}],
    }
    assert fake_client.calls == [("get_prices", ["005930"])]


def test_watch_prices_rejects_negative_interval(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(
            ["watch-prices", "005930", "--interval", "-0.1"],
            config_factory=lambda: make_config(),
            client_factory=lambda config: FakeClient(),
        )

    assert exc_info.value.code == 2
    assert "--interval must be non-negative" in capsys.readouterr().err


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


def test_orders_command_calls_get_orders_without_live_flag():
    exit_code, stdout, _, fake_client = run_cli(
        [
            "orders",
            "--account",
            "7",
            "--status",
            "OPEN",
            "--symbol",
            "005930",
            "--limit",
            "10",
            "--cursor",
            "cursor-1",
        ],
        live=True,
    )

    assert exit_code == 0
    assert json.loads(stdout) == {"orders": [{"orderId": "order-1"}]}
    assert fake_client.calls == [("get_orders", "7", "OPEN", "005930", 10, "cursor-1")]


def test_order_detail_command_calls_get_order_without_live_flag():
    exit_code, stdout, _, fake_client = run_cli(
        ["order-detail", "--account", "7", "--order-id", "order-1"],
        live=True,
    )

    assert exit_code == 0
    assert json.loads(stdout) == {"orderId": "order-1"}
    assert fake_client.calls == [("get_order", "7", "order-1")]


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


def test_cancel_order_without_live_flag_exits_nonzero():
    service = FakeLifecycleService()

    exit_code, _, stderr, fake_client = run_cli(
        ["cancel-order", "--account", "7", "--order-id", "order-1"],
        live=True,
        lifecycle_service_factory=lambda **kwargs: service,
    )

    assert exit_code == 2
    assert "Live order placement requires" in stderr
    assert fake_client.calls == []
    assert service.calls == []


def test_cancel_order_live_calls_lifecycle_service_when_config_enabled():
    service = FakeLifecycleService()
    factory_calls = []

    def lifecycle_service_factory(**kwargs):
        factory_calls.append(kwargs)
        return service

    exit_code, stdout, _, fake_client = run_cli(
        ["cancel-order", "--live", "--account", "7", "--order-id", "order-1"],
        live=True,
        lifecycle_service_factory=lifecycle_service_factory,
    )

    assert exit_code == 0
    assert json.loads(stdout) == {"orderId": "cancel-1"}
    assert factory_calls[0]["client"] is fake_client
    assert service.calls == [("cancel_order", "7", "order-1")]


def test_modify_order_live_calls_lifecycle_service_when_config_enabled():
    service = FakeLifecycleService()

    exit_code, stdout, _, _ = run_cli(
        [
            "modify-order",
            "--live",
            "--account",
            "7",
            "--order-id",
            "order-1",
            "--symbol",
            "005930",
            "--order-type",
            "LIMIT",
            "--quantity",
            "1",
            "--price",
            "70000",
            "--confirm-high-value-order",
        ],
        live=True,
        lifecycle_service_factory=lambda **kwargs: service,
    )

    assert exit_code == 0
    assert json.loads(stdout) == {"orderId": "modify-1"}
    assert service.calls == [
        (
            "modify_order",
            "7",
            "order-1",
            OrderModifyRequest(
                symbol="005930",
                order_type="LIMIT",
                quantity="1",
                price="70000",
                confirm_high_value_order=True,
            ),
        )
    ]


def test_modify_order_rejects_invalid_payload_before_lifecycle_call():
    service = FakeLifecycleService()

    exit_code, _, stderr, _ = run_cli(
        [
            "modify-order",
            "--live",
            "--account",
            "7",
            "--order-id",
            "order-1",
            "--symbol",
            "005930",
            "--order-type",
            "MARKET",
            "--quantity",
            "1",
            "--price",
            "70000",
        ],
        live=True,
        lifecycle_service_factory=lambda **kwargs: service,
    )

    assert exit_code == 2
    assert "MARKET modify must not include price" in stderr
    assert service.calls == []


def test_reconcile_orders_calls_factory_and_prints_report():
    factory_calls = []

    def reconciliation_factory(**kwargs):
        factory_calls.append(kwargs)
        return {"matchedOpenOrderIds": ["order-1"]}

    exit_code, stdout, _, fake_client = run_cli(
        ["reconcile-orders", "--account", "7", "--symbol", "005930"],
        reconciliation_factory=reconciliation_factory,
    )

    assert exit_code == 0
    assert json.loads(stdout) == {"matchedOpenOrderIds": ["order-1"]}
    assert factory_calls[0]["client"] is fake_client
    assert factory_calls[0]["account_seq"] == "7"
    assert factory_calls[0]["symbol"] == "005930"


def test_run_strategy_paper_invokes_runner(tmp_path):
    config = tmp_path / "strategy.toml"
    config.write_text(
        """
        [risk]
        max_order_amount = "1"
        max_daily_notional = "1"
        max_daily_orders = 1
        allowed_symbols = []
        """,
        encoding="utf-8",
    )
    audit_db = tmp_path / "audit.sqlite3"
    calls = []
    fake_runner = FakeRunner()

    def runner_factory(**kwargs):
        calls.append(kwargs)
        return fake_runner

    exit_code, stdout, _, _ = run_cli(
        [
            "run-strategy",
            "--config",
            str(config),
            "--mode",
            "paper",
            "--once",
            "--db-path",
            str(audit_db),
        ],
        runner_factory=runner_factory,
    )

    assert exit_code == 0
    assert calls[0]["mode"] == "paper"
    assert calls[0]["config_path"] == str(config)
    assert fake_runner.calls == [("run_once",)]
    assert json.loads(stdout)["status"] == "COMPLETED"


def test_run_strategy_live_requires_live_flag(tmp_path):
    config = tmp_path / "strategy.toml"
    config.write_text(
        """
        [risk]
        max_order_amount = "1"
        max_daily_notional = "1"
        max_daily_orders = 1
        allowed_symbols = []
        """,
        encoding="utf-8",
    )

    exit_code, _, stderr, _ = run_cli(
        [
            "run-strategy",
            "--config",
            str(config),
            "--mode",
            "live",
            "--account",
            "7",
            "--once",
        ],
        live=True,
        runner_factory=lambda **kwargs: FakeRunner(),
    )

    assert exit_code == 2
    assert "Live order placement requires" in stderr
