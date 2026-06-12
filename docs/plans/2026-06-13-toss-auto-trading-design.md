# Toss Auto Trading Design

## Goal

Build a Python CLI foundation for Toss Securities Open API based auto trading that can handle Korean and US stocks through the same workflow. The first version must be safe by default: it can fetch market/account data and preview orders, while live order placement requires explicit opt-in.

## Official API Evidence

- Official LLM entrypoint: https://developers.tossinvest.com/llms.txt
- Human-readable overview: https://openapi.tossinvest.com/openapi-docs/overview.md
- Canonical OpenAPI document: https://openapi.tossinvest.com/openapi-docs/latest/openapi.json
- OpenAPI version checked: `1.1.1`
- Base API server: `https://openapi.tossinvest.com`

The official documentation states that Toss Securities Open API covers Korean KRX and US stocks for market data, stock info, exchange rate, market calendar, accounts, holdings, and orders. It is currently REST only. All API calls use OAuth 2.0 Client Credentials access tokens. Account, asset, and order APIs also require `X-Tossinvest-Account`.

## Architecture

The app will be a small Python package with a CLI entrypoint. The CLI will call a Toss API client layer, and the client layer will keep authentication, request construction, error parsing, and account headers centralized.

The first implementation will not run an autonomous strategy loop. It will provide the minimum reliable building blocks for one: authentication, unified symbol handling, price/stock/account/holding lookup, order preview, and guarded live order placement.

## Components

1. Configuration
   - Read `.env` keys `API_KEY` and `SECRET_KEY`.
   - Map them to Toss OAuth fields `client_id` and `client_secret`.
   - Support optional `TOSS_BASE_URL` for tests.
   - Support optional `TOSS_LIVE_TRADING=true` for live order permission.

2. Toss API Client
   - `POST /oauth2/token` for OAuth2 Client Credentials.
   - Cache the access token in memory until near expiry.
   - Add `Authorization: Bearer {token}` to all protected calls.
   - Add `X-Tossinvest-Account` only for account-context APIs.
   - Raise typed errors for Toss error envelopes and OAuth errors.

3. Market and Account Commands
   - `prices SYMBOL...`: call `/api/v1/prices` with comma-separated symbols.
   - `stocks SYMBOL...`: call `/api/v1/stocks`.
   - `accounts`: call `/api/v1/accounts`.
   - `holdings [--account ACCOUNT_SEQ] [--symbol SYMBOL]`: call `/api/v1/holdings`.

4. Order Preview and Placement
   - `preview-order`: build and validate a Toss order payload but never submit it.
   - `place-order`: submit only when both `TOSS_LIVE_TRADING=true` and `--live` are present.
   - Generate a `clientOrderId` for idempotency when the user does not provide one.
   - Support quantity-based KR/US orders.
   - Support US market amount-based orders through `orderAmount`.

## Data Flow

1. CLI loads environment configuration.
2. CLI builds a typed request model from arguments.
3. API client obtains or reuses an OAuth token.
4. Market-data commands call Toss APIs with only the bearer token.
5. Account/order commands discover or receive `accountSeq` and include `X-Tossinvest-Account`.
6. Preview commands return the exact payload and safety checks.
7. Live order commands repeat validation, confirm live permission, then call `/api/v1/orders`.

## Safety Rules

- `.env` must be ignored by Git.
- Live order placement is disabled by default.
- Live order placement requires both:
  - environment variable `TOSS_LIVE_TRADING=true`
  - CLI flag `--live`
- Preview mode must never call `/api/v1/orders`.
- `API_KEY` and `SECRET_KEY` must never be logged or printed.
- The client must not automatically refresh tokens on every command if a valid token is already in memory, because issuing a new token invalidates the previous token according to the official docs.
- For buy orders, the app should expose buying-power checks before live placement.
- For sell orders, the app should expose sellable-quantity checks before live placement.

## API Constraints To Preserve

- Korean symbols are 6-digit strings such as `005930`.
- US symbols are ticker strings such as `AAPL`.
- `/api/v1/prices` and `/api/v1/stocks` accept up to 200 comma-separated symbols.
- Account context APIs require `X-Tossinvest-Account`.
- Quantity-based orders require `symbol`, `side`, `orderType`, and `quantity`.
- Limit orders require `price`; market orders must not include `price`.
- US amount-based orders use `orderAmount`, are `MARKET` only, and are regular-session only.
- KR order modification requires `quantity`; US order modification does not support quantity changes. Modification can be implemented after the first order-create foundation.

## Error Handling

OAuth errors use OAuth response fields such as `error` and `error_description`. Other API errors use a Toss envelope under `error` with `requestId`, `code`, `message`, and optional `data`.

The client should include the Toss request id in exceptions when present. Rate-limit responses should surface `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` for future scheduler work.

## Testing

Tests will use mocked HTTP transports and must not call the real Toss API. Required coverage:

- environment loading without exposing secrets
- OAuth token request body and token caching
- authorization and account headers
- market-data symbol joining
- order payload validation for limit, market, quantity, and amount-based orders
- dry-run never submitting orders
- live order requiring both environment and CLI opt-in
- Toss error envelope parsing

## Out Of Scope For First Version

- Autonomous strategy loop
- Scheduled daemon runtime
- Web dashboard
- WebSocket market data
- Order modification/cancel workflow
- Persistent portfolio database
- Tax or performance analytics
