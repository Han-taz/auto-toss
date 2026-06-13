from __future__ import annotations

from typing import Any


def reconcile_open_orders(
    *,
    client: Any,
    audit_store: Any,
    account_seq: int | str,
    symbol: str | None = None,
) -> dict[str, object]:
    broker_payload = client.get_orders(account_seq=account_seq, status="OPEN", symbol=symbol)
    broker_open_ids = set(_extract_order_ids(broker_payload))
    local_submitted_ids = set(audit_store.live_order_ids())

    report = {
        "accountSeq": str(account_seq),
        "symbol": symbol,
        "brokerOpenOrderIds": sorted(broker_open_ids),
        "localSubmittedOrderIds": sorted(local_submitted_ids),
        "matchedOpenOrderIds": sorted(broker_open_ids & local_submitted_ids),
        "brokerOnlyOpenOrderIds": sorted(broker_open_ids - local_submitted_ids),
        "localOnlySubmittedOrderIds": sorted(local_submitted_ids - broker_open_ids),
    }
    audit_store.record_reconciliation(
        account_seq=account_seq,
        symbol=symbol,
        report=report,
    )
    return report


def _extract_order_ids(payload: Any) -> list[str]:
    orders = _orders(payload)
    order_ids = []
    for order in orders:
        if isinstance(order, dict) and isinstance(order.get("orderId"), str):
            order_ids.append(order["orderId"])
    return order_ids


def _orders(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("orders", "items", "result"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                nested = _orders(value)
                if nested:
                    return nested
    return []
