# Auto Trading Safety Core Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the first safe autonomous trading runtime with strategy config loading, risk/preflight checks, paper/live routing, audit storage, CLI wiring, tests, and docs.

**Architecture:** Add small modules around the existing Toss client, order validation, and paper broker. The strategy runner produces normalized order intents, risk/preflight checks decide whether each intent can proceed, execution routes approved intents to paper or live brokers, and an SQLite audit database records every run, check, rejection, and execution.

**Tech Stack:** Python 3.12, stdlib `tomllib`, stdlib `sqlite3`, stdlib `decimal`, `httpx`, `pytest`, `respx`.

---

### Task 1: Toss Client Safety Endpoints

**Files:**
- Modify: `auto_toss/client.py`
- Test: `tests/test_client_endpoints.py`

**Step 1: Write failing tests**

Add tests for the read endpoints the runner needs:

```python
def test_safety_read_endpoints_use_account_header_where_required(respx_mock):
    warnings = respx_mock.get("https://toss.example.test/api/v1/stocks/005930/warnings").mock(
        return_value=httpx.Response(200, json={"result": []})
    )
    limits = respx_mock.get("https://toss.example.test/api/v1/price-limits").mock(
        return_value=httpx.Response(200, json={"result": {"symbol": "005930"}})
    )
    calendar = respx_mock.get("https://toss.example.test/api/v1/market-calendar/KR").mock(
        return_value=httpx.Response(200, json={"result": {"market": "KR"}})
    )
    orders = respx_mock.get("https://toss.example.test/api/v1/orders").mock(
        return_value=httpx.Response(200, json={"result": {"orders": []}})
    )

    client = TossClient(make_config())

    assert client.get_stock_warnings("005930") == []
    assert client.get_price_limits("005930") == {"symbol": "005930"}
    assert client.get_market_calendar("KR") == {"market": "KR"}
    assert client.get_orders(account_seq=7, status="OPEN", symbol="005930") == {"orders": []}

    assert "X-Tossinvest-Account" not in warnings.calls[0].request.headers
    assert limits.calls[0].request.url.params["symbol"] == "005930"
    assert orders.calls[0].request.headers["X-Tossinvest-Account"] == "7"
    assert orders.calls[0].request.url.params["status"] == "OPEN"
```

**Step 2: Run test to verify failure**

Run:

```bash
uv run pytest tests/test_client_endpoints.py::test_safety_read_endpoints_use_account_header_where_required -v
```

Expected: FAIL because the new client methods do not exist.

**Step 3: Implement minimal client methods**

Add:

```python
def get_stock_warnings(self, symbol: str) -> Any:
    return _result(self._request("GET", f"/api/v1/stocks/{symbol}/warnings"))

def get_price_limits(self, symbol: str) -> Any:
    return _result(self._request("GET", "/api/v1/price-limits", params={"symbol": symbol}))

def get_market_calendar(self, market: str) -> Any:
    market = market.upper()
    if market not in {"KR", "US"}:
        raise ValueError("market must be KR or US")
    return _result(self._request("GET", f"/api/v1/market-calendar/{market}"))

def get_orders(
    self,
    *,
    account_seq: int | str,
    status: str,
    symbol: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
) -> Any:
    params: dict[str, Any] = {"status": status}
    if symbol:
        params["symbol"] = symbol
    if limit is not None:
        params["limit"] = limit
    if cursor:
        params["cursor"] = cursor
    return _result(self._request("GET", "/api/v1/orders", params=params, account_seq=account_seq))
```

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_client_endpoints.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add auto_toss/client.py tests/test_client_endpoints.py
git commit -m "feat: add toss safety read endpoints"
```

### Task 2: Strategy Config And Intent Model

**Files:**
- Create: `auto_toss/strategy.py`
- Test: `tests/test_strategy.py`

**Step 1: Write failing tests**

Cover config loading, trigger defaults, and trigger evaluation:

```python
def test_load_strategy_config_normalizes_risk_and_intents(tmp_path):
    path = tmp_path / "strategy.toml"
    path.write_text(
        """
        [risk]
        max_order_amount = "100000"
        max_daily_notional = "300000"
        max_daily_orders = 5
        allowed_symbols = ["005930"]
        kill_switch_file = ".auto_toss/KILL_SWITCH"

        [[intents]]
        symbol = "005930"
        side = "BUY"
        currency = "KRW"
        order_type = "LIMIT"
        quantity = "1"
        price = "70000"
        """,
        encoding="utf-8",
    )

    config = load_strategy_config(path)

    assert config.risk.max_order_amount == Decimal("100000")
    assert config.intents[0].trigger.kind == "always"
    assert config.intents[0].symbol == "005930"

def test_trigger_evaluation_for_price_thresholds():
    below = Trigger(kind="last_price_at_or_below", price=Decimal("70500"))
    above = Trigger(kind="last_price_at_or_above", price=Decimal("70500"))

    assert below.matches(Decimal("70000"))
    assert not below.matches(Decimal("71000"))
    assert above.matches(Decimal("71000"))
    assert not above.matches(Decimal("70000"))
```

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_strategy.py -v
```

Expected: FAIL because `auto_toss.strategy` does not exist.

**Step 3: Implement strategy module**

Create dataclasses:

```python
@dataclass(frozen=True)
class RiskConfig:
    max_order_amount: Decimal
    max_daily_notional: Decimal
    max_daily_orders: int
    allowed_symbols: tuple[str, ...]
    kill_switch_file: str | None = None

@dataclass(frozen=True)
class Trigger:
    kind: str = "always"
    price: Decimal | None = None

    def matches(self, last_price: Decimal | None) -> bool:
        if self.kind == "always":
            return True
        if last_price is None or self.price is None:
            return False
        if self.kind == "last_price_at_or_below":
            return last_price <= self.price
        if self.kind == "last_price_at_or_above":
            return last_price >= self.price
        raise StrategyConfigError(f"Unsupported trigger kind: {self.kind}")

@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    side: str
    currency: str
    order_type: str
    quantity: str | None = None
    price: str | None = None
    order_amount: str | None = None
    client_order_id: str | None = None
    trigger: Trigger = Trigger()

@dataclass(frozen=True)
class StrategyConfig:
    risk: RiskConfig
    intents: tuple[OrderIntent, ...]
```

Use `tomllib.loads`, validate required fields, uppercase side/currency/order
type, parse decimal risk limits, and reject unsupported triggers.

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_strategy.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add auto_toss/strategy.py tests/test_strategy.py
git commit -m "feat: load strategy config"
```

### Task 3: Audit Database

**Files:**
- Create: `auto_toss/audit.py`
- Test: `tests/test_audit.py`

**Step 1: Write failing tests**

```python
def test_audit_store_records_run_checks_and_execution(tmp_path):
    audit = AuditStore(tmp_path / "audit.sqlite3")

    run_id = audit.start_run(mode="paper", config_path="strategy.toml")
    intent_id = audit.record_intent(
        run_id=run_id,
        symbol="005930",
        side="BUY",
        payload={"symbol": "005930"},
    )
    audit.record_check(
        run_id=run_id,
        intent_id=intent_id,
        stage="risk",
        name="allowed_symbol",
        status="PASS",
        reason="allowed",
        evidence={"allowedSymbols": ["005930"]},
    )
    audit.record_execution(
        run_id=run_id,
        intent_id=intent_id,
        mode="paper",
        status="FILLED",
        result={"fillId": "fill-1"},
    )
    audit.complete_run(run_id=run_id, status="COMPLETED")

    assert audit.daily_order_count() == 1
    assert audit.daily_notional() == Decimal("0")
    assert audit.runs()[0]["status"] == "COMPLETED"
```

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_audit.py -v
```

Expected: FAIL because `auto_toss.audit` does not exist.

**Step 3: Implement AuditStore**

Use SQLite tables:

```sql
CREATE TABLE IF NOT EXISTS runs (...);
CREATE TABLE IF NOT EXISTS intents (...);
CREATE TABLE IF NOT EXISTS checks (...);
CREATE TABLE IF NOT EXISTS executions (...);
```

Store JSON evidence via `json.dumps(..., ensure_ascii=False, sort_keys=True)`.
Return integer primary keys for run and intent ids. Implement small read helpers:
`runs()`, `daily_order_count(date=None)`, and `daily_notional(date=None)`.

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_audit.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add auto_toss/audit.py tests/test_audit.py
git commit -m "feat: add auto trading audit store"
```

### Task 4: Local Risk Engine

**Files:**
- Create: `auto_toss/risk.py`
- Test: `tests/test_risk.py`

**Step 1: Write failing tests**

```python
def test_risk_rejects_kill_switch_and_disallowed_symbol(tmp_path):
    kill = tmp_path / "KILL_SWITCH"
    kill.write_text("stop", encoding="utf-8")
    risk = RiskConfig(
        max_order_amount=Decimal("100000"),
        max_daily_notional=Decimal("300000"),
        max_daily_orders=5,
        allowed_symbols=("AAPL",),
        kill_switch_file=str(kill),
    )
    intent = OrderIntent(symbol="005930", side="BUY", currency="KRW", order_type="LIMIT", quantity="1", price="70000")

    results = evaluate_risk(intent=intent, risk=risk, last_price=Decimal("70000"), daily_order_count=0, daily_notional=Decimal("0"))

    assert [result.status for result in results] == ["REJECT", "REJECT"]

def test_risk_rejects_order_amount_and_daily_limits():
    risk = RiskConfig(
        max_order_amount=Decimal("1000"),
        max_daily_notional=Decimal("2000"),
        max_daily_orders=1,
        allowed_symbols=("005930",),
    )
    intent = OrderIntent(symbol="005930", side="BUY", currency="KRW", order_type="LIMIT", quantity="1", price="1500")

    results = evaluate_risk(intent=intent, risk=risk, last_price=Decimal("1500"), daily_order_count=1, daily_notional=Decimal("1000"))

    assert any(result.name == "max_order_amount" and result.status == "REJECT" for result in results)
    assert any(result.name == "max_daily_orders" and result.status == "REJECT" for result in results)
```

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_risk.py -v
```

Expected: FAIL because `auto_toss.risk` does not exist.

**Step 3: Implement risk checks**

Create:

```python
@dataclass(frozen=True)
class CheckResult:
    stage: str
    name: str
    status: str
    reason: str
    evidence: dict[str, object]

    @property
    def passed(self) -> bool:
        return self.status == "PASS"
```

Implement `estimate_notional(intent, last_price)` and `evaluate_risk(...)`.
Return all check results instead of raising so audit can record every reason.

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_risk.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add auto_toss/risk.py tests/test_risk.py
git commit -m "feat: add local risk checks"
```

### Task 5: Preflight Engine

**Files:**
- Create: `auto_toss/preflight.py`
- Test: `tests/test_preflight.py`

**Step 1: Write failing tests**

```python
class FakeClient:
    def __init__(self):
        self.calls = []

    def get_stock_warnings(self, symbol):
        self.calls.append(("warnings", symbol))
        return []

    def get_price_limits(self, symbol):
        self.calls.append(("price_limits", symbol))
        return {"lowerLimitPrice": "60000", "upperLimitPrice": "80000"}

    def get_market_calendar(self, market):
        self.calls.append(("calendar", market))
        return {"sessions": [{"status": "OPEN"}]}

    def get_buying_power(self, *, account_seq, currency):
        self.calls.append(("buying_power", account_seq, currency))
        return {"availableAmount": "1000000"}

    def get_sellable_quantity(self, *, account_seq, symbol):
        self.calls.append(("sellable", account_seq, symbol))
        return {"sellableQuantity": "10"}

    def get_orders(self, *, account_seq, status, symbol=None, limit=None, cursor=None):
        self.calls.append(("orders", account_seq, status, symbol))
        return {"orders": []}

def test_preflight_live_calls_required_toss_checks():
    client = FakeClient()
    intent = OrderIntent(symbol="005930", side="BUY", currency="KRW", order_type="LIMIT", quantity="1", price="70000")

    results = run_preflight(client=client, intent=intent, mode="live", account_seq="1", notional=Decimal("70000"))

    assert all(result.passed for result in results)
    assert ("warnings", "005930") in client.calls
    assert ("orders", "1", "OPEN", "005930") in client.calls
```

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_preflight.py -v
```

Expected: FAIL because `auto_toss.preflight` does not exist.

**Step 3: Implement preflight**

Implement:

- `infer_market(symbol) -> "KR" | "US"`
- `run_preflight(client, intent, mode, account_seq, notional) -> list[CheckResult]`
- parser helpers that tolerate the likely Toss keys and reject when unknown

Keep response handling conservative. If warnings are non-empty, limit prices are
not parseable, market status is not clearly open in live mode, buying power is
below notional, sellable quantity is below order quantity, or an opposite open
order exists, return a `REJECT` check.

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_preflight.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add auto_toss/preflight.py tests/test_preflight.py
git commit -m "feat: add preflight checks"
```

### Task 6: Execution Routing

**Files:**
- Create: `auto_toss/execution.py`
- Test: `tests/test_execution.py`

**Step 1: Write failing tests**

```python
def test_paper_execution_uses_paper_broker_and_not_live_client():
    broker = FakePaperBroker()
    live_client = FakeLiveClient()
    intent = OrderIntent(symbol="005930", side="BUY", currency="KRW", order_type="LIMIT", quantity="1", price="70000")

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
    assert broker.calls == [("005930", "BUY", "KRW", "1", "70000")]
    assert live_client.calls == []

def test_live_execution_requires_existing_live_gate():
    intent = OrderIntent(symbol="005930", side="BUY", currency="KRW", order_type="LIMIT", quantity="1", price="70000")

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
```

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_execution.py -v
```

Expected: FAIL because `auto_toss.execution` does not exist.

**Step 3: Implement execution module**

Create an `ExecutionResult` dataclass and `execute_intent(...)`.

Paper mode:

- select fill price from limit price or supplied last price
- call `PaperBroker.execute_order`

Live mode:

- call `assert_live_order_allowed(config_live_enabled=live_allowed, cli_live=True)`
- build `OrderRequest`
- call `TossClient.create_order(account_seq=account_seq, payload=payload)`

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_execution.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add auto_toss/execution.py tests/test_execution.py
git commit -m "feat: route strategy executions"
```

### Task 7: Strategy Runner Orchestration

**Files:**
- Create: `auto_toss/runner.py`
- Test: `tests/test_runner.py`

**Step 1: Write failing tests**

```python
def test_runner_records_rejected_intent_without_execution(tmp_path):
    config_path = write_strategy(tmp_path, allowed_symbols=["AAPL"], intent_symbol="005930")
    runner = StrategyRunner(
        config_path=config_path,
        mode="paper",
        audit_store=AuditStore(tmp_path / "audit.sqlite3"),
        toss_client=FakeTossClient(last_price="70000"),
        paper_broker=FakePaperBroker(),
        live_allowed=False,
    )

    result = runner.run_once()

    assert result.status == "COMPLETED"
    assert result.executed == 0
    assert result.rejected == 1

def test_runner_executes_paper_intent(tmp_path):
    config_path = write_strategy(tmp_path, allowed_symbols=["005930"], intent_symbol="005930")
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

    assert result.executed == 1
    assert paper.calls
```

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_runner.py -v
```

Expected: FAIL because `auto_toss.runner` does not exist.

**Step 3: Implement runner**

Implement:

- `StrategyRunner.run_once()`
- price fetch before trigger/risk estimation
- trigger skip recorded as a check, not an error
- risk results recorded to audit
- preflight results recorded to audit
- execution result recorded to audit
- run status finalized as `COMPLETED` or `FAILED`

Use fake-friendly constructor injection. Do not instantiate `Config` or
`TossClient` inside the runner.

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_runner.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add auto_toss/runner.py tests/test_runner.py
git commit -m "feat: orchestrate strategy runs"
```

### Task 8: CLI Wiring

**Files:**
- Modify: `auto_toss/cli.py`
- Test: `tests/test_cli_smoke.py`
- Test: `tests/test_cli_commands.py`

**Step 1: Write failing tests**

Add parser smoke coverage:

```python
assert "run-strategy" in commands
```

Add CLI behavior:

```python
def test_run_strategy_paper_invokes_runner(tmp_path):
    config = tmp_path / "strategy.toml"
    config.write_text("[risk]\nmax_order_amount='1'\nmax_daily_notional='1'\nmax_daily_orders=1\nallowed_symbols=[]\n", encoding="utf-8")
    calls = []

    exit_code = main(
        ["run-strategy", "--config", str(config), "--mode", "paper", "--once"],
        runner_factory=lambda **kwargs: calls.append(kwargs) or FakeRunner(),
        config_factory=lambda: make_config(live=False),
    )

    assert exit_code == 0
    assert calls[0]["mode"] == "paper"

def test_run_strategy_live_requires_live_flag(tmp_path):
    config = tmp_path / "strategy.toml"
    config.write_text("[risk]\nmax_order_amount='1'\nmax_daily_notional='1'\nmax_daily_orders=1\nallowed_symbols=[]\n", encoding="utf-8")

    exit_code, _, stderr, _ = run_cli(["run-strategy", "--config", str(config), "--mode", "live", "--once"], live=True)

    assert exit_code == 2
    assert "Live order placement requires" in stderr
```

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_cli_smoke.py tests/test_cli_commands.py -v
```

Expected: FAIL because `run-strategy` is not registered.

**Step 3: Implement CLI command**

Add parser arguments and `main(..., runner_factory=None)`. Build:

- `Config.from_env()`
- `TossClient(config)`
- `PaperBroker(args.paper_db_path)`
- `AuditStore(args.db_path or ".auto_toss/auto_trading.sqlite3")`
- `StrategyRunner(...)`

For looping, call `runner.run_once()` once, `iterations` times, or forever until
interrupt. Print each run result as JSON.

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_cli_smoke.py tests/test_cli_commands.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add auto_toss/cli.py tests/test_cli_smoke.py tests/test_cli_commands.py
git commit -m "feat: add run strategy cli"
```

### Task 9: Documentation And Runtime Policy

**Files:**
- Modify: `README.md`
- Modify: `docs/SOT/architecture.md`
- Create: `docs/llm-wiki/work-units/2026-06-13-auto-trading-safety-core.md`
- Create: `docs/llm-wiki/architecture/auto-trading-safety-core.md`
- Create: `docs/llm-wiki/classes/strategy-runner.md`
- Create: `docs/llm-wiki/classes/risk-and-preflight.md`
- Create: `docs/llm-wiki/infra/auto-trading-audit-db.md`
- Create: `docs/llm-wiki/dead-ends/2026-06-13-auto-trading-safety-core.md`
- Test: `tests/test_docs_and_runtime.py`

**Step 1: Write failing docs test**

Extend docs test:

```python
def test_auto_trading_docs_exist_and_runtime_state_is_ignored():
    required = [
        "docs/llm-wiki/work-units/2026-06-13-auto-trading-safety-core.md",
        "docs/llm-wiki/architecture/auto-trading-safety-core.md",
        "docs/llm-wiki/classes/strategy-runner.md",
        "docs/llm-wiki/classes/risk-and-preflight.md",
        "docs/llm-wiki/infra/auto-trading-audit-db.md",
        "docs/llm-wiki/dead-ends/2026-06-13-auto-trading-safety-core.md",
    ]
    for path in required:
        assert Path(path).exists()
    assert ".auto_toss/" in Path(".gitignore").read_text(encoding="utf-8")
```

**Step 2: Run docs test to verify failure**

Run:

```bash
uv run pytest tests/test_docs_and_runtime.py -v
```

Expected: FAIL because docs do not exist yet.

**Step 3: Update docs**

README must include:

- `run-strategy --mode paper --once`
- live mode gates
- TOML strategy example
- audit DB path
- safety note that this is not financial advice

SOT must include:

- new automation path
- audit DB default path
- paper mode remains default
- live mode requires env gate, CLI gate, risk checks, and preflight checks

llm-wiki pages must describe the new modules, storage, caveats, and future work.

**Step 4: Run docs test**

Run:

```bash
uv run pytest tests/test_docs_and_runtime.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add README.md docs/SOT/architecture.md docs/llm-wiki tests/test_docs_and_runtime.py
git commit -m "docs: document auto trading safety core"
```

### Task 10: Full Verification And Push

**Files:**
- Inspect all changed files.

**Step 1: Run full test suite**

Run:

```bash
uv run pytest
```

Expected: PASS.

**Step 2: Verify secrets/runtime files**

Run:

```bash
git status --short
git check-ignore .env .auto_toss/auto_trading.sqlite3 .auto_toss/paper_trading.sqlite3
```

Expected:

- only intended source/doc/test files are tracked
- `.env` and `.auto_toss/*` runtime state are ignored

**Step 3: Inspect history**

Run:

```bash
git log --oneline -10
```

Expected: task commits are present and ordered.

**Step 4: Push**

Run:

```bash
git push origin main
```

Expected: branch pushes successfully to `https://github.com/Han-taz/auto-toss.git`.
