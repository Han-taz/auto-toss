# Architecture: Order Lifecycle Reliability

## Flows

Read-only inspection:

```text
CLI -> TossClient -> Toss order APIs -> JSON output
```

Live modify/cancel:

```text
CLI live gate -> OrderLifecycleService -> TossClient -> AuditStore
```

Open-order reconciliation:

```text
Toss OPEN orders + AuditStore live submissions -> reconciliation report -> AuditStore
```

## Boundaries

`orders` and `order-detail` expose broker order state without local mutation.
`reconcile-orders` writes only a local report.

`cancel-order` and `modify-order` are live order write commands. They are not
called automatically by `StrategyRunner`; strategy execution still submits new
orders only after risk and preflight checks.

## Broker Truth

Reconciliation treats Toss `OPEN` orders as the broker-side source of truth.
Local submitted IDs come from audited live `SUBMITTED` executions.

`CLOSED` order status is not used as a required reconciliation dependency
because Toss can return unsupported responses for some closed-order queries.

## Retry Behavior

`TossClient` can retry HTTP 429 responses with `Retry-After` when present, or a
bounded exponential backoff from `RetryPolicy`. Non-429 API errors are not
retried.
