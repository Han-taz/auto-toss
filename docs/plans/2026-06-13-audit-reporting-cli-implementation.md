# Audit Reporting CLI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add read-only CLI reporting for automated trading audit data.

**Architecture:** Keep SQLite query ownership inside `AuditStore`, create `auto_toss.reporting` as a JSON-friendly reporting facade, and wire read-only CLI commands before credential loading so audit inspection never requires Toss API credentials. Documentation stays current through README, SOT, and llm-wiki updates.

**Tech Stack:** Python 3.12, stdlib `sqlite3`, stdlib `json`, `pytest`, existing `uv` workflow.

---

### Task 1: AuditStore Run Detail Read Helpers

**Files:**
- Modify: `auto_toss/audit.py`
- Test: `tests/test_audit.py`

**Step 1: Write failing tests**

Add tests:

```python
def test_audit_store_returns_run_detail_with_nested_records(tmp_path):
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
        notional="70000",
    )
    audit.complete_run(run_id=run_id, status="COMPLETED")

    detail = audit.run_detail(run_id)

    assert detail["run"]["id"] == run_id
    assert detail["intents"][0]["payload"]["symbol"] == "005930"
    assert detail["checks"][0]["evidence"]["allowedSymbols"] == ["005930"]
    assert detail["executions"][0]["result"]["fillId"] == "fill-1"


def test_audit_store_returns_none_for_missing_run_detail(tmp_path):
    audit = AuditStore(tmp_path / "audit.sqlite3")

    assert audit.run_detail(999) is None
```

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_audit.py::test_audit_store_returns_run_detail_with_nested_records tests/test_audit.py::test_audit_store_returns_none_for_missing_run_detail -v
```

Expected: FAIL because `AuditStore.run_detail` does not exist.

**Step 3: Implement minimal read helpers**

Add methods:

- `run(run_id)`
- `intents(run_id=None, limit=50)`
- `checks(run_id=None, intent_id=None, limit=50)`
- `executions(run_id=None, intent_id=None, limit=50)`
- `run_detail(run_id)`

Return camelCase dictionaries and decode JSON fields with `_json_value()`.

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_audit.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add auto_toss/audit.py tests/test_audit.py
git commit -m "feat: read audit run details"
```

### Task 2: AuditStore Aggregate Summaries

**Files:**
- Modify: `auto_toss/audit.py`
- Test: `tests/test_audit.py`

**Step 1: Write failing tests**

Add tests:

```python
def test_audit_store_returns_run_summaries_with_counts(tmp_path):
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
    )
    audit.record_execution(
        run_id=run_id,
        intent_id=intent_id,
        mode="paper",
        status="FILLED",
        result={"fillId": "fill-1"},
        notional="70000",
    )

    summary = audit.run_summaries()[0]

    assert summary["id"] == run_id
    assert summary["intentCount"] == 1
    assert summary["checkCount"] == 1
    assert summary["executionCount"] == 1


def test_audit_store_returns_empty_summary_for_empty_db(tmp_path):
    audit = AuditStore(tmp_path / "audit.sqlite3")

    assert audit.summary() == {
        "runs": {"total": 0, "byStatus": {}},
        "executions": {"total": 0, "byStatus": {}},
        "orderEvents": {"total": 0, "byEventType": {}},
        "reconciliations": {"total": 0},
    }
```

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_audit.py::test_audit_store_returns_run_summaries_with_counts tests/test_audit.py::test_audit_store_returns_empty_summary_for_empty_db -v
```

Expected: FAIL because `run_summaries` and `summary` do not exist.

**Step 3: Implement aggregate helpers**

Add methods:

- `run_summaries(limit=20)`
- `summary()`

Use separate count queries or correlated subqueries to avoid join count
multiplication.

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_audit.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add auto_toss/audit.py tests/test_audit.py
git commit -m "feat: summarize audit records"
```

### Task 3: Reporting Module

**Files:**
- Create: `auto_toss/reporting.py`
- Test: `tests/test_reporting.py`

**Step 1: Write failing tests**

Create tests:

```python
import pytest

from auto_toss.audit import AuditStore
from auto_toss.reporting import (
    AuditReportError,
    audit_summary,
    order_events,
    recent_runs,
    reconciliations,
    run_detail,
)


def test_reporting_returns_recent_runs(tmp_path):
    audit = AuditStore(tmp_path / "audit.sqlite3")
    run_id = audit.start_run(mode="paper", config_path="strategy.toml")

    assert recent_runs(audit, limit=5)[0]["id"] == run_id


def test_reporting_raises_for_missing_run(tmp_path):
    audit = AuditStore(tmp_path / "audit.sqlite3")

    with pytest.raises(AuditReportError, match="Audit run not found"):
        run_detail(audit, run_id=999)


def test_reporting_wraps_order_events_reconciliations_and_summary(tmp_path):
    audit = AuditStore(tmp_path / "audit.sqlite3")
    audit.record_order_event(
        event_type="CANCEL",
        order_id="cancel-1",
        source_order_id="order-1",
        status="SUBMITTED",
        payload={},
        result={"orderId": "cancel-1"},
    )
    audit.record_reconciliation(
        account_seq="7",
        symbol="005930",
        report={"matchedOpenOrderIds": ["order-1"]},
    )

    assert order_events(audit)[0]["eventType"] == "CANCEL"
    assert reconciliations(audit)[0]["report"]["matchedOpenOrderIds"] == ["order-1"]
    assert audit_summary(audit)["orderEvents"]["total"] == 1
```

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_reporting.py -v
```

Expected: FAIL because `auto_toss.reporting` does not exist.

**Step 3: Implement reporting facade**

Create:

```python
class AuditReportError(RuntimeError):
    pass

def recent_runs(audit_store, *, limit=20):
    return audit_store.run_summaries(limit=limit)

def run_detail(audit_store, *, run_id):
    detail = audit_store.run_detail(run_id)
    if detail is None:
        raise AuditReportError(f"Audit run not found: {run_id}")
    return detail

def order_events(audit_store, *, limit=20):
    return audit_store.order_events(limit=limit)

def reconciliations(audit_store, *, limit=20):
    return audit_store.reconciliations(limit=limit)

def audit_summary(audit_store):
    return audit_store.summary()
```

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_reporting.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add auto_toss/reporting.py tests/test_reporting.py
git commit -m "feat: add audit reporting facade"
```

### Task 4: CLI Audit Reporting Commands

**Files:**
- Modify: `auto_toss/cli.py`
- Test: `tests/test_cli_smoke.py`
- Test: `tests/test_cli_commands.py`

**Step 1: Write failing tests**

Update parser smoke expected commands:

- `audit-runs`
- `audit-run`
- `audit-order-events`
- `audit-reconciliations`
- `audit-summary`

Add CLI behavior tests using a temporary audit database:

```python
def test_audit_runs_command_prints_recent_run_summaries_without_config(tmp_path):
    audit_db = tmp_path / "audit.sqlite3"
    audit = AuditStore(audit_db)
    audit.start_run(mode="paper", config_path="strategy.toml")

    def fail_config():
        raise AssertionError("audit commands must not load Toss config")

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = main(
        ["audit-runs", "--db-path", str(audit_db), "--limit", "5"],
        config_factory=fail_config,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert json.loads(stdout)[0]["mode"] == "paper"


def test_audit_run_command_prints_detail(tmp_path):
    audit_db = tmp_path / "audit.sqlite3"
    audit = AuditStore(audit_db)
    run_id = audit.start_run(mode="paper", config_path="strategy.toml")

    exit_code, stdout, _, _ = run_cli(
        ["audit-run", "--db-path", str(audit_db), "--run-id", str(run_id)]
    )

    assert exit_code == 0
    assert json.loads(stdout)["run"]["id"] == run_id


def test_audit_run_missing_exits_nonzero(tmp_path):
    exit_code, _, stderr, _ = run_cli(
        ["audit-run", "--db-path", str(tmp_path / "audit.sqlite3"), "--run-id", "999"]
    )

    assert exit_code == 2
    assert "Audit run not found" in stderr
```

Add tests for `audit-order-events`, `audit-reconciliations`, and
`audit-summary`.

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_cli_smoke.py tests/test_cli_commands.py -v
```

Expected: FAIL because commands do not exist.

**Step 3: Implement CLI commands**

Add parsers:

- `audit-runs --db-path --limit`
- `audit-run --db-path --run-id`
- `audit-order-events --db-path --limit`
- `audit-reconciliations --db-path --limit`
- `audit-summary --db-path`

Handle these commands before `config_factory()` is called.

Catch `AuditReportError` in the existing CLI error block and return exit code
`2`.

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_cli_smoke.py tests/test_cli_commands.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add auto_toss/cli.py tests/test_cli_smoke.py tests/test_cli_commands.py
git commit -m "feat: add audit reporting cli"
```

### Task 5: Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/SOT/architecture.md`
- Modify: `docs/llm-wiki/infra/auto-trading-audit-db.md`
- Create: `docs/llm-wiki/work-units/2026-06-13-audit-reporting-cli.md`
- Create: `docs/llm-wiki/architecture/audit-reporting-cli.md`
- Create: `docs/llm-wiki/classes/audit-reporting.md`
- Create: `docs/llm-wiki/dead-ends/2026-06-13-audit-reporting-cli.md`
- Test: `tests/test_docs_and_runtime.py`

**Step 1: Write failing docs test**

Extend required docs list with the new reporting docs.

**Step 2: Run docs test to verify failure**

Run:

```bash
uv run pytest tests/test_docs_and_runtime.py -v
```

Expected: FAIL because new docs do not exist.

**Step 3: Update docs**

README must include examples for:

- `audit-runs`
- `audit-run --run-id`
- `audit-order-events`
- `audit-reconciliations`
- `audit-summary`

SOT must include the reporting path and `auto_toss.reporting` module.

llm-wiki must explain that reporting is read-only and does not require Toss API
credentials.

**Step 4: Run docs test**

Run:

```bash
uv run pytest tests/test_docs_and_runtime.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add README.md docs/SOT/architecture.md docs/llm-wiki tests/test_docs_and_runtime.py
git commit -m "docs: document audit reporting cli"
```

### Task 6: Full Verification, Merge, And Push

**Files:**
- Inspect all changed files.

**Step 1: Run full test suite in worktree**

Run:

```bash
uv run pytest
```

Expected: PASS.

**Step 2: Verify runtime state remains ignored**

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

**Step 6: Cleanup**

Remove the feature worktree and delete the local feature branch after the push
succeeds.
