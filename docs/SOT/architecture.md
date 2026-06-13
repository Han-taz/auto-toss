# Source Of Truth: Architecture

This document is the stable architecture source of truth for `auto-toss`.
Change it only when system boundaries or core architecture change.

## System Boundary

`auto-toss` is a Python CLI for Toss Securities Open API workflows and local trading simulation.

The system has two separate execution paths:

1. Toss API path
   - Uses OAuth2 Client Credentials.
   - Reads market/account data from Toss Securities Open API.
   - Can submit live orders only through `place-order`.
   - Live orders require both `TOSS_LIVE_TRADING=true` and `--live`.

2. Paper trading path
   - Uses local SQLite only.
   - Never calls Toss order APIs.
   - May be paired with Toss market-data commands by the user, but fills are explicit local simulations.

## Core Modules

- `auto_toss.cli`: command-line parsing, JSON output, workflow wiring.
- `auto_toss.config`: environment configuration and credential loading.
- `auto_toss.client`: Toss Open API HTTP client.
- `auto_toss.orders`: Toss order payload validation and live-trading gate.
- `auto_toss.paper`: local SQLite paper trading broker.

## Storage

Runtime state is local and ignored by Git:

- `.env`: Toss credentials.
- `.auto_toss/`: local app runtime state.
- `.auto_toss/paper_trading.sqlite3`: default paper trading database.

## Documentation Boundary

- `docs/SOT`: stable source-of-truth documents.
- `docs/llm-wiki`: daily and operational documents for agents.
- `docs/plans`: dated design and implementation plans.

Documentation freshness is part of the architecture. Work that changes behavior, architecture, infra, or CLI surface is not complete until the relevant documentation is updated.
