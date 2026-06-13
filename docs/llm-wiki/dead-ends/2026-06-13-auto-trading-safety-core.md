# Dead Ends: Auto Trading Safety Core

## Skipped: Strategy First

Starting with moving-average or predictive strategies was rejected. The project
needed execution safety, risk limits, preflight checks, and auditability before
complex strategy logic.

## Skipped: YAML Config

YAML was avoided for the first strategy config because it would add a dependency.
TOML is supported by Python 3.12 through `tomllib`.

## Skipped: Optimistic Preflight Parsing

The preflight layer does not assume eligibility when an API response shape is
unknown. Unknown or unparseable evidence causes a rejection. This may reject some
valid orders, but it is safer for the first live-capable automation milestone.

## Known Caveat

The audit database is local. If users run multiple machines or delete
`.auto_toss/auto_trading.sqlite3`, daily local risk counters will not reflect
the full account history.
