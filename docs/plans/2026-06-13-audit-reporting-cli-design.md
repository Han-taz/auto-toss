# Audit Reporting CLI Design

## Goal

Add an operator-facing reporting layer for the existing automated trading audit
database.

The system already records strategy runs, intents, checks, executions, order
lifecycle events, and reconciliation reports. This milestone makes those records
easy to inspect from the CLI without opening SQLite manually.

This is an observability milestone. It must not submit, cancel, modify, or
reconcile remote orders.

## User Approval

The user approved the recommended next task: audit reporting commands for
automatic trading operations.

Approved scope:

- show recent strategy runs
- show one run with intents, checks, and executions
- show recent order lifecycle events
- show recent reconciliation reports
- show a compact audit summary
- update README, SOT, and llm-wiki docs
- keep output JSON-first for scripts and future UI layers

## Recommended Approach

Create a small reporting module on top of `AuditStore`:

```text
AuditStore read helpers -> auto_toss.reporting -> read-only CLI commands -> JSON
```

This keeps SQL details inside `AuditStore`, presentation shaping inside
`auto_toss.reporting`, and command wiring inside `auto_toss.cli`.

Rejected alternatives:

1. Query SQLite directly from CLI commands
   - Faster for the first command, but SQL would spread into `cli.py` and become
     harder to test.
2. Build a dashboard first
   - Useful later, but the CLI reporting surface is the simpler foundation that
     a dashboard can reuse.
3. Add automatic incident handling
   - Too early. Operators need visibility before automated remediation.

## CLI

Add read-only commands:

```bash
uv run auto-toss audit-runs
uv run auto-toss audit-run --run-id 1
uv run auto-toss audit-order-events
uv run auto-toss audit-reconciliations
uv run auto-toss audit-summary
```

Common options:

- `--db-path`: defaults to `.auto_toss/auto_trading.sqlite3`
- `--limit`: positive integer for list commands, default `20`

Command outputs:

- `audit-runs`: list recent runs with status, mode, timestamps, and aggregate
  counts.
- `audit-run`: one run plus its intents, checks, and executions.
- `audit-order-events`: recent modify/cancel lifecycle events.
- `audit-reconciliations`: recent reconciliation reports.
- `audit-summary`: compact status counts and recent activity counts.

All commands print JSON and do not require Toss API credentials.

## Audit Store Extensions

Add read methods:

- `run_detail(run_id)`
- `checks(run_id=None, intent_id=None, limit=...)`
- `executions(run_id=None, intent_id=None, limit=...)`
- `intents(run_id=None, limit=...)`
- `run_summaries(limit=...)`
- `summary()`

The existing `runs()`, `order_events()`, and `reconciliations()` methods can
remain, but reporting should use aggregate-aware helpers where possible.

## Reporting Module

Create `auto_toss.reporting`.

Functions:

- `recent_runs(audit_store, limit=20)`
- `run_detail(audit_store, run_id)`
- `order_events(audit_store, limit=20)`
- `reconciliations(audit_store, limit=20)`
- `audit_summary(audit_store)`

The module should return plain dictionaries/lists that can be JSON serialized.
It should not print, parse CLI arguments, or open network connections.

## Data Shape

`audit-run` should return:

```json
{
  "run": {},
  "intents": [],
  "checks": [],
  "executions": []
}
```

`audit-summary` should return:

```json
{
  "runs": {},
  "executions": {},
  "orderEvents": {},
  "reconciliations": {}
}
```

Counts can be grouped by status/event type. The exact field names should remain
camelCase to match existing JSON output.

## Error Handling

- Missing run ID returns a validation-style error and CLI exit code `2`.
- Invalid `--limit` follows the existing positive integer parser.
- Missing or empty audit DB returns empty lists/counts rather than crashing.
- Corrupt JSON evidence is already handled by `_json_value()` returning `{}`.

## Testing

Tests must use temporary SQLite databases.

Required coverage:

- `AuditStore` read helpers return nested run data and aggregate counts.
- `auto_toss.reporting` returns JSON-friendly structures.
- CLI commands use the default DB path or injected path correctly.
- `audit-run` exits non-zero for a missing run.
- Parser smoke test includes all new commands.
- Documentation tests require new llm-wiki files.

## Documentation

Update:

- `README.md`: add audit reporting examples.
- `docs/SOT/architecture.md`: add reporting path and module boundary.
- `docs/llm-wiki/infra/auto-trading-audit-db.md`: add reporting usage notes.
- `docs/llm-wiki/work-units/2026-06-13-audit-reporting-cli.md`
- `docs/llm-wiki/architecture/audit-reporting-cli.md`
- `docs/llm-wiki/classes/audit-reporting.md`
- `docs/llm-wiki/dead-ends/2026-06-13-audit-reporting-cli.md`

## Out Of Scope

- Web dashboard
- CSV export
- automatic remediation
- notification delivery
- broker polling beyond the already implemented reconciliation command
