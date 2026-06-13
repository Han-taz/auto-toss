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


def test_audit_store_records_order_events_and_live_order_ids(tmp_path):
    audit = AuditStore(tmp_path / "audit.sqlite3")
    run_id = audit.start_run(mode="live", config_path="strategy.toml")
    intent_id = audit.record_intent(
        run_id=run_id,
        symbol="005930",
        side="BUY",
        payload={"symbol": "005930"},
    )
    audit.record_execution(
        run_id=run_id,
        intent_id=intent_id,
        mode="live",
        status="SUBMITTED",
        result={"orderId": "order-1"},
        notional="70000",
    )
    audit.record_order_event(
        event_type="CANCEL",
        order_id="order-2",
        source_order_id="order-1",
        status="SUBMITTED",
        payload={},
        result={"orderId": "order-2"},
    )

    assert audit.live_order_ids() == ["order-1"]
    assert audit.order_events()[0]["eventType"] == "CANCEL"
    assert audit.order_events()[0]["orderId"] == "order-2"
    assert audit.order_events()[0]["sourceOrderId"] == "order-1"


def test_audit_store_records_reconciliation_report(tmp_path):
    audit = AuditStore(tmp_path / "audit.sqlite3")

    audit.record_reconciliation(
        account_seq="7",
        symbol="005930",
        report={"matchedOpenOrderIds": ["order-1"]},
    )

    report = audit.reconciliations()[0]
    assert report["accountSeq"] == "7"
    assert report["symbol"] == "005930"
    assert report["report"]["matchedOpenOrderIds"] == ["order-1"]


def test_audit_store_returns_run_detail_with_nested_records(tmp_path):
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

    detail = audit.run_detail(run_id)

    assert detail["run"]["id"] == run_id
    assert detail["intents"][0]["payload"]["symbol"] == "005930"
    assert detail["checks"][0]["evidence"]["allowedSymbols"] == ["005930"]
    assert detail["executions"][0]["result"]["fillId"] == "fill-1"


def test_audit_store_returns_none_for_missing_run_detail(tmp_path):
    audit = AuditStore(tmp_path / "audit.sqlite3")

    assert audit.run_detail(999) is None


def test_audit_store_returns_run_summaries_with_counts(tmp_path):
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
        status="PASS",
        reason="allowed",
    )
    audit.record_execution(
        run_id=run_id,
        intent_id=intent_id,
        mode="paper",
        status="FILLED",
        result={"fillId": "fill-1"},
        notional="70000",
    )

    summary = audit.run_summaries()[0]

    assert summary["id"] == run_id
    assert summary["intentCount"] == 1
    assert summary["checkCount"] == 1
    assert summary["executionCount"] == 1


def test_audit_store_returns_empty_summary_for_empty_db(tmp_path):
    audit = AuditStore(tmp_path / "audit.sqlite3")

    assert audit.summary() == {
        "runs": {"total": 0, "byStatus": {}},
        "executions": {"total": 0, "byStatus": {}},
        "orderEvents": {"total": 0, "byEventType": {}},
        "reconciliations": {"total": 0},
    }


def test_audit_store_summary_counts_records_by_status_and_event_type(tmp_path):
    audit = AuditStore(tmp_path / "audit.sqlite3")
    run_id = audit.start_run(mode="live", config_path="strategy.toml")
    intent_id = audit.record_intent(
        run_id=run_id,
        symbol="005930",
        side="BUY",
        payload={"symbol": "005930"},
    )
    audit.record_execution(
        run_id=run_id,
        intent_id=intent_id,
        mode="live",
        status="SUBMITTED",
        result={"orderId": "order-1"},
        notional="70000",
    )
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
    audit.complete_run(run_id=run_id, status="COMPLETED")

    summary = audit.summary()

    assert summary["runs"]["byStatus"] == {"COMPLETED": 1}
    assert summary["executions"]["byStatus"] == {"SUBMITTED": 1}
    assert summary["orderEvents"]["byEventType"] == {"CANCEL": 1}
    assert summary["reconciliations"]["total"] == 1
