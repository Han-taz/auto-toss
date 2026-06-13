# Order Lifecycle Reliability Design

## Goal

Add the next production-readiness layer on top of the auto-trading safety core:
order lifecycle operations, open-order reconciliation, and rate-limit/backoff
handling.

This milestone makes live operation inspectable and recoverable without allowing
the strategy runner to automatically modify or cancel orders.

## User Approval

The user approved continuing with all next steps after the safety core was
merged and pushed. The approved scope is:

- order listing and order detail lookup
- guarded live order cancellation
- guarded live order modification
- audit-backed open-order reconciliation
- rate-limit retry/backoff support
- documentation and tests

## Official API Evidence

- Official overview: https://openapi.tossinvest.com/openapi-docs/overview.md
- Canonical OpenAPI document: https://openapi.tossinvest.com/openapi-docs/latest/openapi.json
- OpenAPI version checked: `1.1.1`
- Base API server: `https://openapi.tossinvest.com`

Relevant official endpoints:

- `GET /api/v1/orders`
- `GET /api/v1/orders/{orderId}`
- `POST /api/v1/orders/{orderId}/modify`
- `POST /api/v1/orders/{orderId}/cancel`

Official constraints to preserve:

- Account and order APIs require `X-Tossinvest-Account`.
- `GET /api/v1/orders?status=OPEN` returns open/pending order groups.
- `GET /api/v1/orders/{orderId}` returns order detail for all statuses.
- `POST /api/v1/orders/{orderId}/modify` returns a new order id.
- `POST /api/v1/orders/{orderId}/cancel` returns a new order id.
- KR modify requires `quantity`.
- US modify does not support `quantity`; price changes only.
- Rate limit headers include `Retry-After`, `X-RateLimit-Limit`,
  `X-RateLimit-Remaining`, and `X-RateLimit-Reset`.

The OpenAPI schema notes that `status=CLOSED` can return
`closed-not-supported`. The CLI will expose the official parameter but docs
should call out that `OPEN` is the primary supported reconciliation path.

## Recommended Approach

Use a CLI-first operating layer:

```text
TossClient lifecycle endpoints
        -> lifecycle payload validation
        -> guarded CLI commands
        -> audit order events
        -> reconciliation reports
```

This keeps manual control over destructive operations while giving the operator
enough tooling to inspect, cancel, modify, and reconcile live orders.

Rejected alternatives:

1. Strategy-driven automatic modify/cancel
   - More autonomous, but too risky before lifecycle visibility and audit are
     proven.
2. Dashboard first
   - Useful later, but it adds UI surface before the core operating primitives
     exist.

## Components

### Toss Client

Add methods:

- `get_order(account_seq, order_id)`
- `modify_order(account_seq, order_id, payload)`
- `cancel_order(account_seq, order_id)`

Keep existing `get_orders(...)`.

Add optional retry support:

- `RetryPolicy(max_attempts, base_delay, max_delay, jitter)`
- retry only `429` responses
- prefer `Retry-After` when present
- fall back to bounded exponential backoff
- preserve current default behavior unless retry policy is enabled

Tests should use injected sleep/random behavior so retry timing is deterministic.

### Order Lifecycle Model

Create `auto_toss.lifecycle` for payload validation and service helpers.

Data types:

- `OrderModifyRequest`
- `build_modify_payload(request)`
- `OrderLifecycleService`

Validation:

- `orderType` is `LIMIT` or `MARKET`
- `LIMIT` requires `price`
- `MARKET` must not include `price`
- KR modify requires `quantity`
- US modify rejects `quantity`
- `confirmHighValueOrder` is passed only when requested

Market inference can remain conservative:

- six numeric characters means KR
- otherwise US

### CLI

Add read-only commands:

- `orders --account ACCOUNT --status OPEN|CLOSED [--symbol SYMBOL] [--limit N] [--cursor CURSOR]`
- `order-detail --account ACCOUNT --order-id ORDER_ID`
- `reconcile-orders --account ACCOUNT [--symbol SYMBOL] [--db-path PATH]`

Add guarded live operation commands:

- `cancel-order --live --account ACCOUNT --order-id ORDER_ID`
- `modify-order --live --account ACCOUNT --order-id ORDER_ID --symbol SYMBOL --order-type LIMIT --price PRICE [--quantity QTY]`

`cancel-order` and `modify-order` require both existing live gates:

- `.env` contains `TOSS_LIVE_TRADING=true`
- CLI includes `--live`

Read-only order commands do not require `--live`.

### Audit Store

Extend the audit database with order-operation records:

- `order_events`: order id, event type, mode, status, payload/result JSON,
  optional source order id
- `reconciliations`: account, symbol filter, counts, raw report JSON

Add read helpers:

- `live_order_ids()`
- `record_order_event(...)`
- `record_reconciliation(...)`
- `reconciliations(limit=...)`

### Reconciliation

Create `auto_toss.reconciliation`.

`reconcile_open_orders(...)` compares:

- broker open order ids from Toss `get_orders(status="OPEN")`
- local submitted live order ids from `AuditStore.live_order_ids()`

Return:

- `brokerOpenOrderIds`
- `localSubmittedOrderIds`
- `matchedOpenOrderIds`
- `brokerOnlyOpenOrderIds`
- `localOnlySubmittedOrderIds`

This is read-only. It does not cancel, modify, or submit orders.

## Data Flow

### Cancel

1. CLI parses `cancel-order`.
2. CLI checks live gates.
3. Lifecycle service optionally records the requested operation.
4. Toss client calls `POST /api/v1/orders/{orderId}/cancel`.
5. Audit store records the returned replacement/cancel order id.
6. CLI prints JSON result.

### Modify

1. CLI parses `modify-order`.
2. CLI checks live gates.
3. CLI builds a validated modify payload.
4. Toss client calls `POST /api/v1/orders/{orderId}/modify`.
5. Audit store records the operation and response.
6. CLI prints JSON result.

### Reconcile

1. CLI calls Toss `get_orders(status="OPEN")`.
2. Audit store loads submitted live order ids.
3. Reconciliation calculates matched, broker-only, and local-only sets.
4. Audit store records the report.
5. CLI prints JSON summary.

## Error Handling

- Config and validation errors return CLI exit code `2`.
- Live operation commands fail before API calls when either live gate is missing.
- Toss API errors preserve request id and rate-limit metadata.
- Retry is limited to 429 responses and bounded by policy.
- Reconciliation never mutates remote order state.

## Testing

Tests must not call real Toss APIs.

Required coverage:

- Toss client detail/modify/cancel endpoints and account headers
- retry policy retries 429 with deterministic sleep
- retry policy stops after configured attempts
- modify payload validation for KR and US constraints
- `cancel-order` and `modify-order` require live gates
- read-only order commands do not require live gates
- lifecycle operations record audit events
- reconciliation identifies matched, broker-only, and local-only open orders
- README, SOT, and llm-wiki docs stay current
- runtime/secrets files remain ignored

## Documentation Updates

Implementation must update:

- `README.md`
- `docs/SOT/architecture.md`
- `docs/llm-wiki/work-units/2026-06-13-order-lifecycle-reliability.md`
- `docs/llm-wiki/architecture/order-lifecycle-reliability.md`
- `docs/llm-wiki/classes/order-lifecycle-service.md`
- `docs/llm-wiki/classes/reconciliation.md`
- `docs/llm-wiki/infra/auto-trading-audit-db.md`
- `docs/llm-wiki/dead-ends/2026-06-13-order-lifecycle-reliability.md`

## Out Of Scope

- strategy-driven automatic order replacement
- strategy-driven automatic cancellation
- web dashboard
- WebSocket market data
- cross-machine audit synchronization
- tax and performance analytics
