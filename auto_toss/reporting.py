from __future__ import annotations

from typing import Any


class AuditReportError(RuntimeError):
    pass


def recent_runs(audit_store: Any, *, limit: int = 20) -> list[dict[str, Any]]:
    return audit_store.run_summaries(limit=limit)


def run_detail(audit_store: Any, *, run_id: int) -> dict[str, Any]:
    detail = audit_store.run_detail(run_id)
    if detail is None:
        raise AuditReportError(f"Audit run not found: {run_id}")
    return detail


def order_events(audit_store: Any, *, limit: int = 20) -> list[dict[str, Any]]:
    return audit_store.order_events(limit=limit)


def reconciliations(audit_store: Any, *, limit: int = 20) -> list[dict[str, Any]]:
    return audit_store.reconciliations(limit=limit)


def audit_summary(audit_store: Any) -> dict[str, Any]:
    return audit_store.summary()
