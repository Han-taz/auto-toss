# auto-toss

Safe Python CLI foundation for Toss Securities Open API.

This project is built from the official Toss Securities Open API documentation:

- https://developers.tossinvest.com/llms.txt
- https://openapi.tossinvest.com/openapi-docs/overview.md
- https://openapi.tossinvest.com/openapi-docs/latest/openapi.json

The API supports Korean and US stocks through the same REST interface. Market-data calls use an OAuth2 bearer token. Account, asset, and order calls also require the `X-Tossinvest-Account` header.

## Setup

Create `.env` in the project root:

```dotenv
API_KEY=your_client_id
SECRET_KEY=your_client_secret
TOSS_LIVE_TRADING=false
```

`.env` is ignored by Git. Do not commit live credentials.

Install and run with `uv`:

```bash
uv run auto-toss --help
```

## Commands

Fetch current prices for Korean and US symbols in one command:

```bash
uv run auto-toss prices 005930 AAPL
```

Watch near-realtime prices by polling the current-price API:

```bash
uv run auto-toss watch-prices 005930 AAPL
```

Run a bounded watch for scripts or tests:

```bash
uv run auto-toss watch-prices 005930 AAPL --interval 1 --iterations 5
```

Fetch stock metadata:

```bash
uv run auto-toss stocks 005930 AAPL
```

Fetch accounts:

```bash
uv run auto-toss accounts
```

Fetch holdings:

```bash
uv run auto-toss holdings --account 1
uv run auto-toss holdings --account 1 --symbol AAPL
```

## Paper Trading

Paper trading is local-only. It does not call Toss order APIs and writes simulated fills to SQLite.

Default paper trading database:

```text
.auto_toss/paper_trading.sqlite3
```

Initialize the local paper account:

```bash
uv run auto-toss paper-init --reset
```

Default starting cash:

- KRW `10000000`
- USD `10000`

Use custom starting cash:

```bash
uv run auto-toss paper-init --reset --krw-cash 5000000 --usd-cash 5000
```

Execute a simulated fill:

```bash
uv run auto-toss paper-order \
  --symbol 005930 \
  --side BUY \
  --currency KRW \
  --quantity 1 \
  --fill-price 70000
```

Inspect portfolio state:

```bash
uv run auto-toss paper-portfolio
uv run auto-toss paper-portfolio --mark-price 005930=71000
```

Inspect fill ledger:

```bash
uv run auto-toss paper-ledger
```

## Automated Strategy Runs

`run-strategy` executes declarative TOML strategy intents through the safety
pipeline:

```text
Strategy config -> Risk checks -> Preflight checks -> Execution -> Audit
```

Paper mode is the default. It uses Toss market-data reads for prices and
preflight evidence, then routes approved fills to the local paper broker:

```bash
uv run auto-toss run-strategy --config strategy.toml --mode paper --once
```

Default audit database:

```text
.auto_toss/auto_trading.sqlite3
```

Minimal strategy example:

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

Supported trigger kinds:

- `always`
- `last_price_at_or_below`
- `last_price_at_or_above`

Live strategy execution requires all live gates and preflight checks:

```bash
uv run auto-toss run-strategy \
  --config strategy.toml \
  --mode live \
  --live \
  --account 1 \
  --once
```

If `TOSS_LIVE_TRADING=true` is not set, `--live` is missing, or risk/preflight
checks reject an intent, the runner records the decision and does not submit a
live order.

Preview a limit order without submitting it:

```bash
uv run auto-toss preview-order \
  --symbol 005930 \
  --side BUY \
  --order-type LIMIT \
  --quantity 1 \
  --price 70000
```

Preview a US amount-based market order:

```bash
uv run auto-toss preview-order \
  --symbol AAPL \
  --side BUY \
  --order-type MARKET \
  --order-amount 100.50
```

## Live Orders

Order preview is the default safe workflow and never calls `/api/v1/orders`.

Live order placement requires both software gates:

1. `.env` contains `TOSS_LIVE_TRADING=true`
2. The command includes `--live`

Example:

```bash
uv run auto-toss place-order \
  --live \
  --account 1 \
  --symbol 005930 \
  --side BUY \
  --order-type LIMIT \
  --quantity 1 \
  --price 70000
```

If either gate is missing, the command exits without submitting an order.

## Safety Notes

This project is not financial advice. Live trading can lose money. Start with `preview-order`, inspect the payload, and use small test orders only after you confirm your Toss Securities API access, account sequence, order permissions, and market hours.

Tests use mocked HTTP responses and do not call the real Toss API.
