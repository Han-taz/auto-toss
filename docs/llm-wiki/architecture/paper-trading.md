# Paper Trading Architecture

Paper trading is a local simulation subsystem.

It deliberately does not use Toss order endpoints. This separation keeps strategy testing safe while live order placement remains behind the existing two-gate live trading mechanism.

## Flow

1. User initializes paper state with `paper-init`.
2. User executes simulated fills with `paper-order`.
3. `PaperBroker` validates cash, position, side, currency, quantity, and fill price.
4. `PaperBroker` writes immutable fills and updates cash/positions in SQLite.
5. User inspects state with `paper-portfolio` and `paper-ledger`.

## Future Strategy Integration

A future strategy runner should produce proposed orders, then route them to paper trading by default. Live routing should remain opt-in and continue to require explicit live-trading gates.
