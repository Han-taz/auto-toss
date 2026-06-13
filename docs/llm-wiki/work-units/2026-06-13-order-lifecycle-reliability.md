# Work Unit: Order Lifecycle Reliability

## Goal

Add reliable order inspection, guarded live modify/cancel commands, local order
event audit records, open-order reconciliation, and basic 429 retry behavior.

## Implemented

- Added Toss client methods for:
  - order list
  - order detail
  - order modify
  - order cancel
- Added optional `RetryPolicy` for 429 responses.
- Added `auto_toss.lifecycle` for modify payload validation and lifecycle event
  recording.
- Added `auto_toss.reconciliation` to compare Toss `OPEN` orders with local
  live submissions.
- Extended `AuditStore` with `order_events`, `reconciliations`, and
  `live_order_ids()`.
- Added CLI commands:
  - `orders`
  - `order-detail`
  - `cancel-order`
  - `modify-order`
  - `reconcile-orders`

## Safety Rules

`orders`, `order-detail`, and `reconcile-orders` are read-only. They do not
require `--live`.

`cancel-order` and `modify-order` are live order writes. They require both:

- `TOSS_LIVE_TRADING=true`
- command-level `--live`

## Verification

Relevant tests:

```bash
uv run pytest tests/test_client_endpoints.py tests/test_client_requests.py tests/test_lifecycle.py tests/test_audit.py tests/test_reconciliation.py tests/test_cli_smoke.py tests/test_cli_commands.py tests/test_docs_and_runtime.py -v
```

Run the full suite before claiming completion:

```bash
uv run pytest
```
