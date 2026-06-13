# SQLite Paper Trading Infra

## Runtime Path

Default database:

```text
.auto_toss/paper_trading.sqlite3
```

`.auto_toss/` is ignored by Git.

## Tables

- `accounts`: default logical account.
- `cash_balances`: cash by currency.
- `positions`: symbol/currency position quantity and average cost.
- `fills`: immutable simulated fill ledger.

## Decimal Storage

Numeric values are stored as decimal strings. Python code uses `Decimal` for arithmetic to avoid float drift.

## Operational Notes

Use `--db-path` for tests, experiments, or multiple local simulations. Do not commit SQLite runtime databases.
