# Work Unit: Auto Trading Safety Core

## Goal

Add the first automated strategy runtime while preserving paper-by-default
behavior and explicit live-trading gates.

## Implemented

- Added Toss read endpoints needed by preflight:
  - stock warnings
  - price limits
  - market calendar
  - open orders
- Added TOML strategy config loading in `auto_toss.strategy`.
- Added SQLite audit storage in `auto_toss.audit`.
- Added local risk checks in `auto_toss.risk`.
- Added conservative Toss read-only preflight checks in `auto_toss.preflight`.
- Added paper/live execution routing in `auto_toss.execution`.
- Added `StrategyRunner` orchestration in `auto_toss.runner`.
- Added `run-strategy` CLI command.

## Safety Rules

Paper mode is the default. Live mode requires:

- `TOSS_LIVE_TRADING=true`
- `--mode live`
- `--live`
- `--account`
- passing local risk checks
- passing Toss preflight checks

Rejected and skipped intents are recorded in the audit database and do not submit
orders.

## Verification

Relevant tests:

```bash
uv run pytest tests/test_strategy.py tests/test_audit.py tests/test_risk.py tests/test_preflight.py tests/test_execution.py tests/test_runner.py tests/test_cli_smoke.py tests/test_cli_commands.py tests/test_docs_and_runtime.py -v
```

Run the full suite before claiming completion:

```bash
uv run pytest
```
