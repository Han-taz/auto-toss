# 2026-06-13 Paper Trading Work Unit

## Objective

Add local paper trading before strategy automation so order logic can be tested without real Toss order submission.

## Implemented Behavior

- Added local SQLite-backed paper trading storage.
- Added simulated BUY and SELL fills.
- Added cash balances for KRW and USD.
- Added positions with quantity and average cost.
- Added realized P&L on SELL.
- Added portfolio and ledger views.
- Added paper CLI commands:
  - `paper-init`
  - `paper-order`
  - `paper-portfolio`
  - `paper-ledger`

## Defaults

- KRW paper cash: `10000000`
- USD paper cash: `10000`
- Default DB path: `.auto_toss/paper_trading.sqlite3`

## Completion Notes

Docs must be updated whenever paper trading behavior changes. This note should be extended if future work adds quote-based fills, commission, tax, slippage, multiple accounts, or strategy integration.
