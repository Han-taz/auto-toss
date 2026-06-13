# Infra: Auto Trading Audit DB

## Default Path

```text
.auto_toss/auto_trading.sqlite3
```

`.auto_toss/` is ignored by Git and must remain runtime-only.

## Owner

`auto_toss.audit.AuditStore`

## Tables

- `runs`: mode, config path, status, timestamps
- `intents`: normalized strategy intent payload per run
- `checks`: strategy, risk, and preflight decisions
- `executions`: paper fill or live submission result

JSON evidence is stored as text with stable key ordering. Monetary and quantity
values are stored as decimal strings.

## Daily Limits

`AuditStore.daily_order_count()` and `AuditStore.daily_notional()` are used by
the risk engine to enforce daily order and notional limits from local execution
history.

## Operational Notes

Deleting the audit DB removes local daily limit history. Do not delete it during
live operation unless intentionally resetting local automation state.
