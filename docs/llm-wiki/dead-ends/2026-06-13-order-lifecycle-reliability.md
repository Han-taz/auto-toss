# Dead Ends: Order Lifecycle Reliability

## Closed-Order Reconciliation

Do not depend on `status=CLOSED` as the reconciliation source of truth yet.
Toss documentation notes that closed-order queries can be unsupported in some
cases. The implemented reconciliation path uses `OPEN` orders only.

## Automatic Cancel Or Modify

This work intentionally does not let strategies automatically cancel or modify
orders. The CLI supports guarded manual lifecycle operations first. Automatic
order management needs separate policy, risk limits, and tests.

## Unbounded Retries

The client does not retry indefinitely. 429 handling is bounded by
`RetryPolicy.max_attempts`; all other HTTP errors still fail immediately.

## Paper Lifecycle Events

Paper trading does not simulate broker-native cancel/modify order replacement.
The lifecycle service is for Toss live order operations and local audit records.
