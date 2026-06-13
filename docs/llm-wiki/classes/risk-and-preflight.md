# Risk And Preflight Notes

## Modules

- `auto_toss.risk`
- `auto_toss.preflight`

## Risk Checks

Risk checks are local and run before Toss preflight calls:

- kill switch file
- allowed symbol list
- positive numeric values
- estimated notional
- max order amount
- max daily order count
- max daily notional

Risk checks return `CheckResult` objects instead of raising so every decision can
be recorded in audit storage.

## Preflight Checks

Preflight checks use Toss read APIs and are conservative:

- stock warnings
- limit price bounds
- market calendar in live mode
- buying power for live buys
- sellable quantity for live sells
- opposite open orders in live mode

If the response cannot be interpreted safely, the check rejects the intent.

## Market Inference

The first implementation infers market by symbol shape:

- six digits: `KR`
- otherwise: `US`

This is intentionally simple and should be replaced only when official metadata
is integrated into the runner.
