# PaperBroker Class Notes

## Module

`auto_toss.paper`

## Purpose

`PaperBroker` owns local paper trading state and simulated fills. It is intentionally separate from `TossClient` so paper trading cannot accidentally submit live Toss orders.

## Important Methods

- `initialize(reset=False, krw_cash="10000000", usd_cash="10000")`
  - Creates the SQLite schema and default account.
  - Sets KRW and USD cash balances.

- `execute_order(symbol, side, currency, quantity, fill_price, client_order_id=None)`
  - Simulates a fill at an explicit fill price.
  - BUY reduces cash and updates average cost.
  - SELL reduces position and records realized P&L.

- `portfolio(mark_prices=None)`
  - Returns cash, positions, realized P&L, and optional mark-to-market values.

- `ledger(limit=50)`
  - Returns latest simulated fills first.

## Error Type

`PaperTradingError` is used for local validation failures such as insufficient cash, insufficient position, invalid currency, and invalid decimal input.
