# Reconciliation Function Notes

## Module

`auto_toss.reconciliation`

## Entry Point

`reconcile_open_orders(client, audit_store, account_seq, symbol=None)`

## Responsibility

Fetch Toss `OPEN` orders and compare their order IDs with locally audited live
submissions.

The returned report contains:

- `brokerOpenOrderIds`
- `localSubmittedOrderIds`
- `matchedOpenOrderIds`
- `brokerOnlyOpenOrderIds`
- `localOnlySubmittedOrderIds`

## Local State Dependency

Local submitted order IDs come from `AuditStore.live_order_ids()`, which reads
live executions recorded with status `SUBMITTED`.

If the audit database was deleted, recreated, or not used for earlier live
orders, reconciliation can legitimately report broker-only open orders.

## Caveat

This function does not resolve discrepancies. It records and returns the report
so a human or later automation layer can decide whether to cancel, modify, or
ignore each order.
