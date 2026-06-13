# Order Lifecycle Reliability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add order lifecycle commands, guarded modify/cancel operations, open-order reconciliation, and 429 retry/backoff support.

**Architecture:** Extend `TossClient` with official order lifecycle endpoints and optional retry policy. Add `auto_toss.lifecycle` for modify payload validation and operation recording, `auto_toss.reconciliation` for read-only local-vs-broker comparison, extend `AuditStore` for order events and reconciliation reports, then expose everything through CLI commands.

**Tech Stack:** Python 3.12, stdlib `sqlite3`, stdlib `decimal`, stdlib `time`, `httpx`, `pytest`, `respx`.

---

### Task 1: Toss Client Order Lifecycle Endpoints

**Files:**
- Modify: `auto_toss/client.py`
- Test: `tests/test_client_endpoints.py`

**Step 1: Write failing tests**

Add tests:

```python
@respx.mock
def test_order_lifecycle_methods_use_account_header_and_payloads():
    mock_token()
    detail = respx.get("https://toss.example.test/api/v1/orders/order-1").mock(
        return_value=httpx.Response(200, json={"result": {"orderId": "order-1"}})
    )
    modify = respx.post("https://toss.example.test/api/v1/orders/order-1/modify").mock(
        return_value=httpx.Response(200, json={"result": {"orderId": "order-2"}})
    )
    cancel = respx.post("https://toss.example.test/api/v1/orders/order-1/cancel").mock(
        return_value=httpx.Response(200, json={"result": {"orderId": "order-3"}})
    )

    client = TossClient(make_config())

    assert client.get_order(account_seq=7, order_id="order-1") == {"orderId": "order-1"}
    assert client.modify_order(account_seq=7, order_id="order-1", payload={"orderType": "LIMIT", "quantity": "1", "price": "70000"}) == {"orderId": "order-2"}
    assert client.cancel_order(account_seq=7, order_id="order-1") == {"orderId": "order-3"}

    assert detail.calls[0].request.headers["X-Tossinvest-Account"] == "7"
    assert modify.calls[0].request.headers["X-Tossinvest-Account"] == "7"
    assert cancel.calls[0].request.headers["X-Tossinvest-Account"] == "7"
    assert cancel.calls[0].request.read() == b"{}"
```

**Step 2: Run test to verify failure**

Run:

```bash
uv run pytest tests/test_client_endpoints.py::test_order_lifecycle_methods_use_account_header_and_payloads -v
```

Expected: FAIL because the new client methods do not exist.

**Step 3: Implement endpoints**

Add:

```python
def get_order(self, *, account_seq: int | str, order_id: str) -> Any:
    return _result(self._request("GET", f"/api/v1/orders/{order_id}", account_seq=account_seq))

def modify_order(self, *, account_seq: int | str, order_id: str, payload: dict[str, Any]) -> Any:
    return _result(self._request("POST", f"/api/v1/orders/{order_id}/modify", json=payload, account_seq=account_seq))

def cancel_order(self, *, account_seq: int | str, order_id: str) -> Any:
    return _result(self._request("POST", f"/api/v1/orders/{order_id}/cancel", json={}, account_seq=account_seq))
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
git commit -m "feat: add order lifecycle endpoints"
```

### Task 2: 429 Retry Policy

**Files:**
- Modify: `auto_toss/client.py`
- Test: `tests/test_client_requests.py`

**Step 1: Write failing tests**

Add tests:

```python
def test_retry_policy_retries_429_using_retry_after(respx_mock):
    sleeps = []
    route = respx_mock.get("https://toss.example.test/api/v1/accounts").mock(
        side_effect=[
            httpx.Response(429, json={"error": {"code": "rate-limit-exceeded", "message": "slow"}}, headers={"Retry-After": "2"}),
            httpx.Response(200, json={"result": [{"accountSeq": 7}]}),
        ]
    )

    client = TossClient(
        make_config(),
        retry_policy=RetryPolicy(max_attempts=2, base_delay=1, max_delay=4),
        sleep=sleeps.append,
    )

    assert client.get_accounts() == [{"accountSeq": 7}]
    assert route.call_count == 2
    assert sleeps == [2.0]

def test_retry_policy_raises_after_attempts_exhausted(respx_mock):
    respx_mock.get("https://toss.example.test/api/v1/accounts").mock(
        return_value=httpx.Response(429, json={"error": {"code": "rate-limit-exceeded", "message": "slow"}})
    )
    client = TossClient(make_config(), retry_policy=RetryPolicy(max_attempts=2), sleep=lambda _: None)

    with pytest.raises(TossRateLimitError):
        client.get_accounts()
```

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_client_requests.py::test_retry_policy_retries_429_using_retry_after tests/test_client_requests.py::test_retry_policy_raises_after_attempts_exhausted -v
```

Expected: FAIL because `RetryPolicy` and retry constructor arguments do not exist.

**Step 3: Implement retry policy**

Add:

```python
@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1
    base_delay: float = 1.0
    max_delay: float = 4.0
```

Update `TossClient.__init__(..., retry_policy=None, sleep=time.sleep)`.

In `_request`, loop attempts. On 429:

- build `TossRateLimitError`
- if attempts remain, sleep `Retry-After` if parseable
- otherwise sleep `min(base_delay * 2 ** (attempt - 1), max_delay)`
- retry request
- raise after attempts exhausted

Do not retry non-429 errors.

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_client_requests.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add auto_toss/client.py tests/test_client_requests.py
git commit -m "feat: retry rate limited requests"
```

### Task 3: Lifecycle Payload Validation And Service

**Files:**
- Create: `auto_toss/lifecycle.py`
- Test: `tests/test_lifecycle.py`

**Step 1: Write failing tests**

Add tests for modify payloads and service operations:

```python
def test_build_modify_payload_enforces_kr_quantity_and_limit_price():
    payload = build_modify_payload(
        OrderModifyRequest(symbol="005930", order_type="LIMIT", quantity="1", price="70000")
    )
    assert payload == {"orderType": "LIMIT", "quantity": "1", "price": "70000"}

def test_build_modify_payload_rejects_us_quantity():
    with pytest.raises(OrderValidationError, match="US modify"):
        build_modify_payload(OrderModifyRequest(symbol="AAPL", order_type="LIMIT", quantity="1", price="200"))

def test_lifecycle_service_records_cancel_event():
    service = OrderLifecycleService(client=FakeClient(), audit_store=FakeAudit())
    result = service.cancel_order(account_seq="7", order_id="order-1")
    assert result == {"orderId": "cancel-1"}
    assert service.audit_store.events[0]["event_type"] == "CANCEL"
```

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_lifecycle.py -v
```

Expected: FAIL because `auto_toss.lifecycle` does not exist.

**Step 3: Implement lifecycle**

Create:

- `OrderModifyRequest`
- `build_modify_payload`
- `OrderLifecycleService.cancel_order`
- `OrderLifecycleService.modify_order`

The service calls Toss client methods and records audit events when an
`audit_store` is provided.

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_lifecycle.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add auto_toss/lifecycle.py tests/test_lifecycle.py
git commit -m "feat: validate order lifecycle operations"
```

### Task 4: Audit Order Events And Reconciliation Storage

**Files:**
- Modify: `auto_toss/audit.py`
- Test: `tests/test_audit.py`

**Step 1: Write failing tests**

Add:

```python
def test_audit_store_records_order_events_and_live_order_ids(tmp_path):
    audit = AuditStore(tmp_path / "audit.sqlite3")
    run_id = audit.start_run(mode="live", config_path="strategy.toml")
    intent_id = audit.record_intent(run_id=run_id, symbol="005930", side="BUY", payload={})
    audit.record_execution(run_id=run_id, intent_id=intent_id, mode="live", status="SUBMITTED", result={"orderId": "order-1"}, notional="70000")
    audit.record_order_event(event_type="CANCEL", order_id="order-2", source_order_id="order-1", status="SUBMITTED", payload={}, result={"orderId": "order-2"})

    assert audit.live_order_ids() == ["order-1"]
    assert audit.order_events()[0]["eventType"] == "CANCEL"

def test_audit_store_records_reconciliation_report(tmp_path):
    audit = AuditStore(tmp_path / "audit.sqlite3")
    audit.record_reconciliation(account_seq="7", symbol="005930", report={"matchedOpenOrderIds": ["order-1"]})
    assert audit.reconciliations()[0]["report"]["matchedOpenOrderIds"] == ["order-1"]
```

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_audit.py -v
```

Expected: FAIL because methods/tables do not exist.

**Step 3: Implement audit extensions**

Add `order_events` and `reconciliations` tables in `_create_schema`.
Add methods:

- `record_order_event`
- `order_events(limit=50)`
- `live_order_ids`
- `record_reconciliation`
- `reconciliations(limit=50)`

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_audit.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add auto_toss/audit.py tests/test_audit.py
git commit -m "feat: audit order lifecycle events"
```

### Task 5: Open Order Reconciliation

**Files:**
- Create: `auto_toss/reconciliation.py`
- Test: `tests/test_reconciliation.py`

**Step 1: Write failing tests**

```python
def test_reconcile_open_orders_classifies_broker_and_local_orders():
    audit = FakeAudit(["local-1", "local-only"])
    client = FakeClient({"orders": [{"orderId": "local-1"}, {"orderId": "broker-only"}]})

    report = reconcile_open_orders(client=client, audit_store=audit, account_seq="7", symbol="005930")

    assert report["matchedOpenOrderIds"] == ["local-1"]
    assert report["brokerOnlyOpenOrderIds"] == ["broker-only"]
    assert report["localOnlySubmittedOrderIds"] == ["local-only"]
    assert audit.reports
```

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_reconciliation.py -v
```

Expected: FAIL because `auto_toss.reconciliation` does not exist.

**Step 3: Implement reconciliation**

Create `reconcile_open_orders(client, audit_store, account_seq, symbol=None)`.
Fetch `client.get_orders(account_seq=..., status="OPEN", symbol=symbol)`, extract
order ids, compare with `audit_store.live_order_ids()`, record report, return it.

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_reconciliation.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add auto_toss/reconciliation.py tests/test_reconciliation.py
git commit -m "feat: reconcile open orders"
```

### Task 6: CLI Order Lifecycle Commands

**Files:**
- Modify: `auto_toss/cli.py`
- Test: `tests/test_cli_smoke.py`
- Test: `tests/test_cli_commands.py`

**Step 1: Write failing tests**

Add parser commands:

- `orders`
- `order-detail`
- `cancel-order`
- `modify-order`
- `reconcile-orders`

Add command behavior tests:

- read-only `orders` calls fake client without live flag
- `order-detail` calls fake client without live flag
- `cancel-order` requires live gates and records through service
- `modify-order` requires live gates and validates payload
- `reconcile-orders` calls reconciliation factory and prints report

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_cli_smoke.py tests/test_cli_commands.py -v
```

Expected: FAIL because commands do not exist.

**Step 3: Implement CLI commands**

Wire:

- `orders` -> `client.get_orders`
- `order-detail` -> `client.get_order`
- `cancel-order` -> live gate -> `OrderLifecycleService.cancel_order`
- `modify-order` -> live gate -> `OrderLifecycleService.modify_order`
- `reconcile-orders` -> `reconcile_open_orders`

Inject optional `lifecycle_service_factory` and `reconciliation_factory` for tests.

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_cli_smoke.py tests/test_cli_commands.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add auto_toss/cli.py tests/test_cli_smoke.py tests/test_cli_commands.py
git commit -m "feat: add order lifecycle cli"
```

### Task 7: Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/SOT/architecture.md`
- Modify: `docs/llm-wiki/infra/auto-trading-audit-db.md`
- Create: `docs/llm-wiki/work-units/2026-06-13-order-lifecycle-reliability.md`
- Create: `docs/llm-wiki/architecture/order-lifecycle-reliability.md`
- Create: `docs/llm-wiki/classes/order-lifecycle-service.md`
- Create: `docs/llm-wiki/classes/reconciliation.md`
- Create: `docs/llm-wiki/dead-ends/2026-06-13-order-lifecycle-reliability.md`
- Test: `tests/test_docs_and_runtime.py`

**Step 1: Write failing docs test**

Extend required docs list with the new lifecycle docs.

**Step 2: Run docs test to verify failure**

Run:

```bash
uv run pytest tests/test_docs_and_runtime.py -v
```

Expected: FAIL because new docs do not exist.

**Step 3: Update docs**

README must include order list/detail/cancel/modify/reconcile examples and live
gate warning for cancel/modify.

SOT must include lifecycle modules and audit tables.

llm-wiki must explain operation boundaries, caveats, and local audit behavior.

**Step 4: Run docs test**

Run:

```bash
uv run pytest tests/test_docs_and_runtime.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add README.md docs/SOT/architecture.md docs/llm-wiki tests/test_docs_and_runtime.py
git commit -m "docs: document order lifecycle reliability"
```

### Task 8: Full Verification, Merge, And Push

**Files:**
- Inspect all changed files.

**Step 1: Run full test suite**

Run:

```bash
uv run pytest
```

Expected: PASS.

**Step 2: Verify ignored runtime state**

Run:

```bash
git status --short
git check-ignore .env .auto_toss/auto_trading.sqlite3 .auto_toss/paper_trading.sqlite3
```

Expected: clean source state and ignored secrets/runtime state.

**Step 3: Merge to main**

Fast-forward merge the feature branch into `main`.

**Step 4: Re-run full test suite on main**

Run:

```bash
uv run pytest
```

Expected: PASS.

**Step 5: Push**

Run:

```bash
git push origin main
```

Expected: `origin/main` updated successfully.
