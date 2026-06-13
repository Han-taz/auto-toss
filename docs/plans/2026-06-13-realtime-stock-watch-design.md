# Realtime Stock Watch Design

## Goal

Add a CLI workflow for near-realtime stock lookup by repeatedly polling Toss Securities current-price market data for one or more Korean or US symbols.

## API Evidence

The official Toss Securities OpenAPI document version `1.1.1` describes the Market Data group as realtime-like quote data and says WebSocket support is planned for later. The existing client already calls `GET /api/v1/prices`, which is the right API foundation for a polling watch command.

## Approach

Add a `watch-prices` command alongside the existing one-shot `prices` command. It will call `TossClient.get_prices(symbols)` repeatedly, print each snapshot as a JSON object on its own line, flush output after every snapshot, and sleep between polls.

The command accepts `--interval` for polling cadence and optional `--iterations` for bounded runs. Without `--iterations`, it keeps polling until interrupted. Tests use dependency-injected sleep and a finite iteration count, so no test contacts Toss or waits on real time.

## Error Handling

The command reuses existing config, authentication, and Toss API error handling. `KeyboardInterrupt` exits with status `130` after printing any completed snapshots. `--interval` must be non-negative and `--iterations` must be positive when provided.

## Testing

Tests cover parser exposure, repeated client calls, JSON-lines streaming, no sleep after the final bounded iteration, input validation, and interrupt behavior. Existing mocked HTTP client tests remain unchanged because the command reuses `get_prices`.
