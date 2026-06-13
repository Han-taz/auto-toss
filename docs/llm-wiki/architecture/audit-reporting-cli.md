# Architecture: Audit Reporting CLI

## Flow

```text
CLI -> auto_toss.reporting -> AuditStore -> SQLite
```

Reporting commands are handled before `Config.from_env()` and `TossClient`
construction. This keeps local audit inspection available even when Toss
credentials are missing or invalid.

## Commands

- `audit-runs`: recent strategy runs with aggregate record counts.
- `audit-run`: one run with intents, checks, and executions.
- `audit-order-events`: recent modify/cancel lifecycle events.
- `audit-reconciliations`: recent open-order reconciliation reports.
- `audit-summary`: status and event counts across the audit database.

## Data Shape

All outputs are JSON and use camelCase field names. Nested JSON payloads stored
in SQLite are decoded before returning.

## Non-Goals

This layer is not a dashboard, exporter, alert system, or automated remediation
engine. It is the stable CLI inspection surface that those later layers can use.
