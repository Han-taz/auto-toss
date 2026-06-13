# Auto Trading Safety Core Design

## Goal

Add the first autonomous trading runtime for `auto-toss` without weakening the
existing safety posture. The runtime should make real stock auto trading
possible, but paper trading remains the default execution path and live trading
requires explicit opt-in plus risk and preflight approval.

This milestone turns the existing safe building blocks into a controlled
automation pipeline:

```text
Strategy config -> OrderIntent -> RiskCheck -> PreflightCheck -> Execution -> Audit
```

## User Approval

The approved first milestone is the safety core:

- strategy runner
- risk and preflight engine
- paper/live execution routing
- persistent audit database
- documentation and tests

Order lifecycle expansion and more advanced strategies are intentionally
deferred until the runner has reliable safety and observability.

## Official API Evidence

- Official LLM entrypoint: https://developers.tossinvest.com/llms.txt
- Human-readable overview: https://openapi.tossinvest.com/openapi-docs/overview.md
- Canonical OpenAPI document: https://openapi.tossinvest.com/openapi-docs/latest/openapi.json
- OpenAPI version checked: `1.1.1`
- Base API server: `https://openapi.tossinvest.com`

The official API currently provides REST endpoints for market data, stock
metadata, market calendars, account assets, order creation, order modification,
order cancellation, order history, buying power, sellable quantity, and
commissions. Account, asset, and order APIs require `X-Tossinvest-Account`.

Relevant safety APIs for this milestone:

- `GET /api/v1/market-calendar/KR`
- `GET /api/v1/market-calendar/US`
- `GET /api/v1/stocks/{symbol}/warnings`
- `GET /api/v1/price-limits`
- `GET /api/v1/prices`
- `GET /api/v1/buying-power`
- `GET /api/v1/sellable-quantity`
- `GET /api/v1/orders?status=OPEN`
- `POST /api/v1/orders`

Rate limits are enforced by client and API group. The runner must avoid bursty
polling and must surface 429 metadata rather than hiding it.

## Architecture

The runtime will remain a Python CLI package. New automation modules should sit
beside the existing client, order, and paper trading modules:

- `auto_toss.strategy`: load declarative strategy config and produce order
  intents.
- `auto_toss.risk`: enforce local risk policy before any preflight or execution.
- `auto_toss.preflight`: call Toss read APIs that prove an order is currently
  eligible.
- `auto_toss.execution`: route approved orders to paper or live brokers.
- `auto_toss.audit`: store run, intent, check, rejection, and execution records
  in SQLite.
- `auto_toss.runner`: coordinate one-shot and looped strategy runs.

Existing modules remain responsible for their current boundaries:

- `auto_toss.client`: Toss HTTP transport, auth, account headers, and API errors.
- `auto_toss.orders`: Toss order payload validation and live gate.
- `auto_toss.paper`: local paper fills and portfolio state.
- `auto_toss.cli`: command parsing and workflow wiring.

## CLI

Add `run-strategy`:

```bash
uv run auto-toss run-strategy \
  --config strategy.toml \
  --mode paper \
  --once
```

Live execution requires every gate:

```bash
uv run auto-toss run-strategy \
  --config strategy.toml \
  --mode live \
  --live \
  --account 1 \
  --once
```

Arguments:

- `--config`: required strategy TOML file.
- `--mode`: `paper` or `live`, default `paper`.
- `--live`: required only when `--mode live`.
- `--account`: required only when `--mode live`.
- `--interval`: polling interval for looped runs.
- `--iterations`: optional bounded loop count for scripts and tests.
- `--once`: shorthand for a single run.
- `--db-path`: optional audit database path.
- `--paper-db-path`: optional paper trading database path.

`--once` and `--iterations` cannot be combined.

## Strategy Config

Use TOML so the first version can use Python's standard `tomllib` parser.

Initial strategy type: declarative order intents with optional price triggers.
This is intentionally simple and deterministic. The runner should prove the
pipeline before adding technical indicators or external signal engines.

Example:

```toml
[risk]
max_order_amount = "100000"
max_daily_notional = "300000"
max_daily_orders = 5
allowed_symbols = ["005930", "AAPL"]
kill_switch_file = ".auto_toss/KILL_SWITCH"

[[intents]]
symbol = "005930"
side = "BUY"
currency = "KRW"
order_type = "LIMIT"
quantity = "1"
price = "70000"
client_order_id = "demo-005930-buy-1"

[intents.trigger]
kind = "last_price_at_or_below"
price = "70500"
```

Supported trigger kinds in the first version:

- `always`
- `last_price_at_or_below`
- `last_price_at_or_above`

An intent with no trigger behaves as `always`.

## Risk Rules

Risk checks are local and run before Toss preflight calls:

- reject when the configured kill switch file exists
- reject symbols not present in `allowed_symbols`
- reject non-positive quantity, price, or amount values
- reject estimated order amount above `max_order_amount`
- reject runs that exceed `max_daily_orders`
- reject runs that exceed `max_daily_notional`
- reject live mode unless the existing `TOSS_LIVE_TRADING=true` and `--live`
  gates both pass

Estimated notional:

- quantity limit order: `quantity * price`
- quantity market order: `quantity * last price`
- amount market order: `orderAmount`

If the notional cannot be estimated, the order is rejected instead of guessed.

## Preflight Checks

Preflight checks run after local risk checks and before execution.

For both paper and live modes:

- fetch current prices for trigger and market-order notional estimation
- validate stock warnings and reject active warning types by default
- validate price limits for limit orders when the endpoint returns bounds

For live mode only:

- check market calendar for the symbol's market when the market can be inferred
- check buying power before buys
- check sellable quantity before sells
- check open orders for the same symbol to reject opposite pending orders
- preserve Toss API request ids and error details in audit records

The first implementation may keep market inference simple:

- six numeric characters means KR
- otherwise US

If an API response shape is broader than the current implementation understands,
the runner records the response and rejects the order rather than assuming
eligibility.

## Execution Routing

Paper execution:

- routes to `PaperBroker.execute_order`
- uses the configured order price for limit orders
- uses the last fetched price for market orders
- records a simulated fill in the existing paper database

Live execution:

- reuses `build_order_payload`
- requires `assert_live_order_allowed`
- calls `TossClient.create_order`
- stores the returned Toss order fields and any request id metadata available

The first milestone does not modify or cancel orders automatically.

## Audit Storage

Add a SQLite audit database. Default path:

```text
.auto_toss/auto_trading.sqlite3
```

Tables:

- `runs`: mode, config path, started/completed timestamps, status
- `intents`: normalized strategy output per run
- `checks`: risk and preflight check results with reason and raw evidence
- `executions`: paper fill id or live Toss order id/result

All monetary and quantity values are stored as decimal strings. Raw Toss
response fragments are stored as JSON text when they are useful for later
debugging.

## Error Handling

The runner distinguishes:

- config errors: invalid TOML, unsupported strategy fields, missing risk limits
- rejected orders: risk or preflight checks blocked the intent
- execution errors: paper broker errors or Toss API errors
- rate limit errors: preserve retry headers from `TossRateLimitError`

A rejected intent is not a process failure when at least one run completes and
the rejection is recorded. Invalid configuration and unexpected execution
exceptions return CLI exit code `2`.

## Testing

Tests must not call real Toss APIs.

Required coverage:

- parser registers `run-strategy`
- strategy TOML loads into normalized intents
- trigger decisions for below, above, and always
- local risk rejects kill switch, disallowed symbol, excessive order amount,
  excessive daily notional, and excessive daily order count
- preflight calls warning, price limit, buying power, sellable quantity, and
  open order APIs through a fake client
- paper mode routes to `PaperBroker` and never calls `create_order`
- live mode requires `--live` and `TOSS_LIVE_TRADING=true`
- audit DB records runs, rejected checks, and executions
- README, SOT, and llm-wiki docs stay current
- `.auto_toss/` runtime state remains ignored

## Documentation Updates

Implementation must update:

- `README.md` for `run-strategy` usage and config examples
- `docs/SOT/architecture.md` for the new automation path and audit DB
- `docs/llm-wiki/work-units/2026-06-13-auto-trading-safety-core.md`
- `docs/llm-wiki/architecture/auto-trading-safety-core.md`
- `docs/llm-wiki/classes/strategy-runner.md`
- `docs/llm-wiki/classes/risk-and-preflight.md`
- `docs/llm-wiki/infra/auto-trading-audit-db.md`
- `docs/llm-wiki/dead-ends/2026-06-13-auto-trading-safety-core.md`

## Out Of Scope

- predictive or ML strategies
- order modification and cancellation automation
- web dashboard
- WebSocket market data
- multi-account orchestration
- tax, fee, and performance analytics beyond the audit trail
- unsupervised live trading without explicit `--live` and env gates
