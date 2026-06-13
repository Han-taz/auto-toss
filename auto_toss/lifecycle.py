from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from auto_toss.orders import OrderValidationError


@dataclass(frozen=True)
class OrderModifyRequest:
    symbol: str
    order_type: str
    quantity: str | None = None
    price: str | None = None
    confirm_high_value_order: bool = False


@dataclass(frozen=True)
class OrderLifecycleService:
    client: Any
    audit_store: Any | None = None

    def cancel_order(self, *, account_seq: int | str, order_id: str) -> Any:
        result = self.client.cancel_order(account_seq=account_seq, order_id=order_id)
        self._record_event(
            event_type="CANCEL",
            order_id=_result_order_id(result),
            source_order_id=order_id,
            status="SUBMITTED",
            payload={},
            result=result,
        )
        return result

    def modify_order(
        self,
        *,
        account_seq: int | str,
        order_id: str,
        request: OrderModifyRequest,
    ) -> Any:
        payload = build_modify_payload(request)
        result = self.client.modify_order(
            account_seq=account_seq,
            order_id=order_id,
            payload=payload,
        )
        self._record_event(
            event_type="MODIFY",
            order_id=_result_order_id(result),
            source_order_id=order_id,
            status="SUBMITTED",
            payload=payload,
            result=result,
        )
        return result

    def _record_event(
        self,
        *,
        event_type: str,
        order_id: str | None,
        source_order_id: str,
        status: str,
        payload: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        if self.audit_store is None:
            return
        self.audit_store.record_order_event(
            event_type=event_type,
            order_id=order_id,
            source_order_id=source_order_id,
            status=status,
            payload=payload,
            result=result,
        )


def build_modify_payload(request: OrderModifyRequest) -> dict[str, object]:
    order_type = request.order_type.upper()
    if order_type not in {"LIMIT", "MARKET"}:
        raise OrderValidationError("orderType must be LIMIT or MARKET.")

    is_kr = _is_kr_symbol(request.symbol)
    if is_kr and request.quantity is None:
        raise OrderValidationError("KR modify requires quantity.")
    if not is_kr and request.quantity is not None:
        raise OrderValidationError("US modify does not support quantity.")

    payload: dict[str, object] = {"orderType": order_type}
    if request.quantity is not None:
        payload["quantity"] = request.quantity

    if order_type == "LIMIT":
        if request.price is None:
            raise OrderValidationError("LIMIT modify requires price.")
        payload["price"] = request.price
    elif request.price is not None:
        raise OrderValidationError("MARKET modify must not include price.")

    if request.confirm_high_value_order:
        payload["confirmHighValueOrder"] = True

    return payload


def _is_kr_symbol(symbol: str) -> bool:
    return len(symbol) == 6 and symbol.isdigit()


def _result_order_id(result: Any) -> str | None:
    if isinstance(result, dict) and isinstance(result.get("orderId"), str):
        return result["orderId"]
    return None
