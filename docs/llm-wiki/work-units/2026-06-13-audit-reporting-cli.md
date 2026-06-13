# Work Unit: Audit Reporting CLI

## Goal

Expose automated trading audit records through read-only JSON CLI commands.

## Implemented

- Added `AuditStore` read helpers for run detail, nested intents/checks/executions,
  recent run summaries, and aggregate audit summary counts.
- Added `auto_toss.reporting` as a JSON-friendly facade.
- Added CLI commands:
  - `audit-runs`
  - `audit-run`
  - `audit-order-events`
  - `audit-reconciliations`
  - `audit-summary`

## Boundary

Audit reporting reads only local SQLite state. It does not load Toss API
credentials, call Toss APIs, submit orders, cancel orders, modify orders, or run
reconciliation.

## Verification

Relevant tests:

```bash
uv run pytest tests/test_audit.py tests/test_reporting.py tests/test_cli_smoke.py tests/test_cli_commands.py tests/test_docs_and_runtime.py -v
```

Run the full suite before claiming completion:

```bash
uv run pytest
```
