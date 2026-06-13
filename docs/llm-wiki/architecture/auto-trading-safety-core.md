# Architecture: Auto Trading Safety Core

## Pipeline

Automated strategy execution uses this pipeline:

```text
TOML strategy -> OrderIntent -> RiskCheck -> PreflightCheck -> Execution -> Audit
```

`StrategyRunner` coordinates the pipeline and receives all dependencies through
constructor injection. It does not create `Config` or `TossClient`; the CLI wires
those objects.

## Modes

Paper mode:

- fetches Toss market data for prices and preflight evidence
- records risk/preflight results
- executes approved quantity orders through `PaperBroker`
- never calls Toss order creation

Live mode:

- requires CLI and environment live gates
- runs the same local risk checks
- runs live-only preflight checks for calendar, buying power, sellable quantity,
  and opposite open orders
- submits approved orders through `TossClient.create_order`

## Conservative Defaults

Unknown or unparseable preflight evidence rejects an intent. The system should
prefer a recorded rejection over an unsafe assumption.

## Current Limits

- Strategy config is declarative TOML only.
- Triggers are price threshold or always-on.
- No automatic modify/cancel workflow exists yet.
- No WebSocket data path exists yet.
