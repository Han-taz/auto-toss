# Source Of Truth: Architecture

This document is the stable architecture source of truth for `auto-toss`.
Change it only when system boundaries or core architecture change.

## System Boundary

`auto-toss` is a Python CLI for Toss Securities Open API workflows and local trading simulation.

The system has separate execution paths:

1. Toss API path
   - Uses OAuth2 Client Credentials.
   - Reads market/account data from Toss Securities Open API.
   - Can submit live order create, modify, and cancel operations only through explicit CLI commands.
   - Live order writes require both `TOSS_LIVE_TRADING=true` and `--live`.

2. Paper trading path
   - Uses local SQLite only.
   - Never calls Toss order APIs.
   - May be paired with Toss market-data commands by the user, but fills are explicit local simulations.

3. Automated strategy path
   - Uses `run-strategy` to load TOML strategy intents.
   - Runs local risk checks, Toss read-only preflight checks, execution routing, and audit recording.
   - Defaults to paper execution.
   - Live execution requires `TOSS_LIVE_TRADING=true`, `--mode live`, `--live`, `--account`, passing risk checks, and passing preflight checks.
   - Rejected or skipped intents are audit records, not live orders.

4. Order lifecycle path
   - Uses `orders`, `order-detail`, and `reconcile-orders` for read-only order inspection.
   - Uses `cancel-order` and `modify-order` for live order lifecycle writes.
   - Records local lifecycle events and reconciliation reports in the automated trading audit database.
   - Reconciliation treats Toss `OPEN` orders as the primary broker truth and compares them with locally audited live submissions.

5. Audit reporting path
   - Uses `audit-runs`, `audit-run`, `audit-order-events`, `audit-reconciliations`, and `audit-summary`.
   - Reads only the local automated trading audit database.
   - Does not require Toss API credentials.
   - Does not mutate local or remote trading state.

## Core Modules

- `auto_toss.cli`: command-line parsing, JSON output, workflow wiring.
- `auto_toss.config`: environment configuration and credential loading.
- `auto_toss.client`: Toss Open API HTTP client.
- `auto_toss.orders`: Toss order payload validation and live-trading gate.
- `auto_toss.lifecycle`: order modify/cancel validation, dispatch, and lifecycle event recording.
- `auto_toss.reconciliation`: local-vs-broker open order comparison.
- `auto_toss.reporting`: JSON-friendly read-only audit report facade.
- `auto_toss.paper`: local SQLite paper trading broker.
- `auto_toss.strategy`: TOML strategy config and order intent model.
- `auto_toss.risk`: local kill switch, symbol allowlist, notional, and daily limit checks.
- `auto_toss.preflight`: Toss read-only eligibility checks before execution.
- `auto_toss.execution`: paper/live execution routing.
- `auto_toss.audit`: local SQLite run, check, execution, lifecycle event, and reconciliation storage.
- `auto_toss.runner`: strategy run orchestration.

## Storage

Runtime state is local and ignored by Git:

- `.env`: Toss credentials.
- `.auto_toss/`: local app runtime state.
- `.auto_toss/paper_trading.sqlite3`: default paper trading database.
- `.auto_toss/auto_trading.sqlite3`: default automated strategy, order lifecycle, and reporting audit database.

## Documentation Boundary

- `docs/SOT`: stable source-of-truth documents.
- `docs/llm-wiki`: daily and operational documents for agents.
- `docs/plans`: dated design and implementation plans.

Documentation freshness is part of the architecture. Work that changes behavior, architecture, infra, or CLI surface is not complete until the relevant documentation is updated.
