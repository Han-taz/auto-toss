# StrategyRunner Class Notes

## Module

`auto_toss.runner`

## Responsibility

`StrategyRunner` turns a strategy config into one audited run. It loads TOML
config, fetches prices, evaluates triggers, records checks, routes approved
orders, and finalizes the run status.

## Constructor Inputs

- `config_path`: TOML strategy file.
- `mode`: `paper` or `live`.
- `audit_store`: `AuditStore` instance.
- `toss_client`: Toss client or fake with required read/order methods.
- `paper_broker`: `PaperBroker` instance or fake.
- `live_allowed`: config-level live trading boolean.
- `account_seq`: Toss account sequence for live execution.

## Run Semantics

`run_once()` returns a `RunResult` with:

- `run_id`
- `status`
- `executed`
- `rejected`
- `skipped`

Trigger misses are `skipped`. Risk or preflight failures are `rejected`.
Approved executions increment `executed`.

## Audit Boundary

The runner records:

- run start and completion
- normalized intent payloads
- strategy trigger decisions
- risk check results
- preflight check results
- paper fills or live order submission results
