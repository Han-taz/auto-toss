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
