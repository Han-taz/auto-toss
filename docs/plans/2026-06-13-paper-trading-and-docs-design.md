# Paper Trading And Docs System Design

## Goal

Add local paper trading so strategies can be tested without sending orders to Toss Securities, and add a documentation system that future agents can use as a stable source of truth and daily work log.

## User Requirements

- Implement paper trading mode.
- Create SOT documents under `docs/SOT`.
- Create an `llm-wiki` under `docs/llm-wiki`.
- The wiki must have folders for work-unit notes, dead-end notes, class/method docs, architecture docs, and infra docs.
- The docs must let future agents understand how the system should be implemented and what work has already happened.
- Documentation updates are mandatory after work; documentation freshness is a completion condition.

## Paper Trading Scope

Paper trading will be local-only and will never call Toss order APIs. It may use market prices fetched through the existing Toss market-data client, but order execution and portfolio state live in a local SQLite database.

Default paper account balances:

- KRW cash: `10000000`
- USD cash: `10000`

The defaults are intentionally conservative and configurable at account creation time.

## Paper Trading Commands

Add these CLI commands:

- `paper-init`: create or reset a local paper trading database and account.
- `paper-order`: execute a simulated order using an explicit fill price.
- `paper-portfolio`: show paper cash, positions, realized P&L, and mark-to-market values when prices are supplied.
- `paper-ledger`: list simulated orders/fills.

The first version will require explicit `--fill-price` for `paper-order`. This avoids silently pretending that a live market quote is an exact executable fill. Later strategy-runner work can add quote-based fill models.

## Storage

Use SQLite from the Python standard library. Default path:

```text
.auto_toss/paper_trading.sqlite3
```

The `.auto_toss/` runtime directory must be ignored by Git.

Tables:

- `accounts`: one logical paper account with base cash balances.
- `cash_balances`: currency to cash amount.
- `positions`: symbol, currency, quantity, average cost.
- `fills`: immutable simulated fill ledger.

All monetary and quantity values are stored as decimal strings to avoid float drift.

## Fill Model

Initial fill model:

- BUY reduces cash and increases position.
- SELL reduces position and increases cash.
- BUY cannot exceed cash in that currency.
- SELL cannot exceed position quantity.
- Average cost updates on BUY.
- Realized P&L is recorded on SELL as `(fill_price - average_cost) * quantity`.

Supported currencies are `KRW` and `USD`. The CLI requires `--currency` for paper orders so KR and US symbols can be handled through the same flow without fragile symbol guessing.

## Documentation System

Create:

```text
docs/SOT/
docs/llm-wiki/
docs/llm-wiki/work-units/
docs/llm-wiki/dead-ends/
docs/llm-wiki/classes/
docs/llm-wiki/architecture/
docs/llm-wiki/infra/
```

`docs/SOT/architecture.md` is the stable source of truth for system boundaries. It should change only when the architecture changes.

`docs/SOT/documentation-policy.md` defines a mandatory rule: every behavior, architecture, infra, or CLI change must update relevant docs before completion.

`docs/llm-wiki/README.md` explains the folder map for agents. The wiki is allowed to grow daily and should contain operational notes that are too detailed or too time-specific for SOT.

## Error Handling

Paper trading errors are local validation errors:

- database not initialized
- invalid currency
- insufficient cash
- insufficient position
- non-positive quantity or fill price

They should produce CLI exit code `2`, consistent with current validation and API errors.

## Testing

Tests must not call Toss APIs. Required coverage:

- initializing the SQLite schema and default cash balances
- custom initial cash balances
- BUY fill updates cash and position
- SELL fill updates cash, position, and realized P&L
- insufficient cash and insufficient position failures
- CLI command behavior for init/order/portfolio/ledger
- `.auto_toss/` is ignored
- documentation structure and policy files exist

## Out Of Scope

- automatic strategy runner
- quote-based fill model
- slippage/commission/tax model
- multiple named paper accounts
- exchange-rate conversion
- live order integration
