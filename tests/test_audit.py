from decimal import Decimal

from auto_toss.audit import AuditStore


def test_audit_store_records_run_checks_and_execution(tmp_path):
    audit = AuditStore(tmp_path / "audit.sqlite3")

    run_id = audit.start_run(mode="paper", config_path="strategy.toml")
    intent_id = audit.record_intent(
        run_id=run_id,
        symbol="005930",
        side="BUY",
        payload={"symbol": "005930", "side": "BUY"},
    )
    audit.record_check(
        run_id=run_id,
        intent_id=intent_id,
        stage="risk",
        name="allowed_symbol",
        status="PASS",
        reason="allowed",
        evidence={"allowedSymbols": ["005930"]},
    )
    audit.record_execution(
        run_id=run_id,
        intent_id=intent_id,
        mode="paper",
        status="FILLED",
        result={"fillId": "fill-1"},
        notional="70000",
    )
    audit.complete_run(run_id=run_id, status="COMPLETED")

    assert audit.daily_order_count() == 1
    assert audit.daily_notional() == Decimal("70000")
    assert audit.runs()[0]["status"] == "COMPLETED"
    assert audit.runs()[0]["mode"] == "paper"


def test_audit_store_records_rejected_checks_without_counting_execution(tmp_path):
    audit = AuditStore(tmp_path / "audit.sqlite3")

    run_id = audit.start_run(mode="paper", config_path="strategy.toml")
    intent_id = audit.record_intent(
        run_id=run_id,
        symbol="005930",
        side="BUY",
        payload={"symbol": "005930"},
    )
    audit.record_check(
        run_id=run_id,
        intent_id=intent_id,
        stage="risk",
        name="allowed_symbol",
        status="REJECT",
        reason="symbol not allowed",
        evidence={"allowedSymbols": ["AAPL"]},
    )
    audit.complete_run(run_id=run_id, status="COMPLETED")

    assert audit.daily_order_count() == 0
    assert audit.daily_notional() == Decimal("0")
