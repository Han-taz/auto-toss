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
- `order_events`: live order modify/cancel events and Toss results
- `reconciliations`: local-vs-broker open order comparison reports

JSON evidence is stored as text with stable key ordering. Monetary and quantity
values are stored as decimal strings.

## Daily Limits

`AuditStore.daily_order_count()` and `AuditStore.daily_notional()` are used by
the risk engine to enforce daily order and notional limits from local execution
history.

## Reporting

Read-only CLI commands expose audit data without loading Toss API credentials:

- `audit-runs`
- `audit-run`
- `audit-order-events`
- `audit-reconciliations`
- `audit-summary`

These commands call `auto_toss.reporting`, which delegates SQL ownership to
`AuditStore`.

## Operational Notes

Deleting the audit DB removes local daily limit history. Do not delete it during
live operation unless intentionally resetting local automation state.

Deleting the audit DB also removes local live submission IDs used by
`reconcile-orders`. After a reset, broker-only open orders may be legitimate
orders that were submitted before the local audit history was recreated.
