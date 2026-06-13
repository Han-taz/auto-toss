# Audit Reporting Notes

## Modules

- `auto_toss.audit`
- `auto_toss.reporting`

## AuditStore Additions

`AuditStore` owns SQL reads for:

- `run(run_id)`
- `intents(run_id=None, limit=50)`
- `checks(run_id=None, intent_id=None, limit=50)`
- `executions(run_id=None, intent_id=None, limit=50)`
- `run_detail(run_id)`
- `run_summaries(limit=20)`
- `summary()`

`run_detail()` returns `None` when the run does not exist.

## Reporting Facade

`auto_toss.reporting` exposes:

- `recent_runs(audit_store, limit=20)`
- `run_detail(audit_store, run_id=...)`
- `order_events(audit_store, limit=20)`
- `reconciliations(audit_store, limit=20)`
- `audit_summary(audit_store)`

`run_detail()` raises `AuditReportError` for missing run IDs so the CLI can
return exit code `2` with a clear message.

## CLI Boundary

Reporting functions return plain Python dictionaries and lists. They do not
print, parse arguments, open network connections, or construct Toss clients.
