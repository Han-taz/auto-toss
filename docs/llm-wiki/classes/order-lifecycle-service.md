# OrderLifecycleService Class Notes

## Module

`auto_toss.lifecycle`

## Responsibility

`OrderLifecycleService` wraps live order cancel and modify operations so they
can be audited consistently.

It does not enforce the CLI live gate. Callers must run
`assert_live_order_allowed()` before invoking live write methods.

## Modify Validation

`build_modify_payload()` validates Toss modify constraints:

- `orderType` must be `LIMIT` or `MARKET`.
- Korean symbols require `quantity`.
- US symbols reject `quantity`.
- `LIMIT` requires `price`.
- `MARKET` must not include `price`.
- `confirmHighValueOrder` is included only when explicitly requested.

## Audit Boundary

When an `audit_store` is provided, the service records:

- event type: `CANCEL` or `MODIFY`
- new order ID returned by Toss, when present
- source order ID
- request payload
- Toss result payload

The service returns the Toss result unchanged.
