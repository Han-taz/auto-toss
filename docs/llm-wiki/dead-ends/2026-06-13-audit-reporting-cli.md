# Dead Ends: Audit Reporting CLI

## Dashboard First

A dashboard was deferred. The CLI reporting surface is smaller, easier to test,
and can become the data source for a dashboard later.

## Direct SQL In CLI

SQL was kept out of `auto_toss.cli`. `AuditStore` remains the database boundary,
and `auto_toss.reporting` shapes data for JSON output.

## Credential Loading

Reporting commands intentionally run before Toss config loading. Requiring API
credentials for local audit inspection would make incident review harder when
credential configuration is broken.

## Automatic Remediation

The reporting layer does not cancel, modify, or reconcile orders. It reports
state only; remediation policy needs a separate design and safety gates.
