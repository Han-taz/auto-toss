import pytest

from auto_toss.audit import AuditStore
from auto_toss.reporting import (
    AuditReportError,
    audit_summary,
    order_events,
    recent_runs,
    reconciliations,
    run_detail,
)


def test_reporting_returns_recent_runs(tmp_path):
    audit = AuditStore(tmp_path / "audit.sqlite3")
    run_id = audit.start_run(mode="paper", config_path="strategy.toml")

    assert recent_runs(audit, limit=5)[0]["id"] == run_id


def test_reporting_raises_for_missing_run(tmp_path):
    audit = AuditStore(tmp_path / "audit.sqlite3")

    with pytest.raises(AuditReportError, match="Audit run not found"):
        run_detail(audit, run_id=999)


def test_reporting_wraps_order_events_reconciliations_and_summary(tmp_path):
    audit = AuditStore(tmp_path / "audit.sqlite3")
    audit.record_order_event(
        event_type="CANCEL",
        order_id="cancel-1",
        source_order_id="order-1",
        status="SUBMITTED",
        payload={},
        result={"orderId": "cancel-1"},
    )
    audit.record_reconciliation(
        account_seq="7",
        symbol="005930",
        report={"matchedOpenOrderIds": ["order-1"]},
    )

    assert order_events(audit)[0]["eventType"] == "CANCEL"
    assert reconciliations(audit)[0]["report"]["matchedOpenOrderIds"] == ["order-1"]
    assert audit_summary(audit)["orderEvents"]["total"] == 1
