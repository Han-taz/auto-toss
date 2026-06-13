from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from auto_toss.orders import (
    OrderRequest,
    OrderValidationError,
    assert_live_order_allowed,
    build_order_payload,
)
from auto_toss.strategy import OrderIntent


class ExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExecutionResult:
    mode: str
    status: str
    result: dict[str, Any]
    notional: str


def execute_intent(
    *,
    intent: OrderIntent,
    mode: str,
    paper_broker: Any,
    live_client: Any,
    account_seq: int | str | None,
    live_allowed: bool,
    fill_price: Decimal,
) -> ExecutionResult:
    if mode == "paper":
        return _execute_paper(intent=intent, paper_broker=paper_broker, fill_price=fill_price)
    if mode == "live":
        return _execute_live(
            intent=intent,
            live_client=live_client,
            account_seq=account_seq,
            live_allowed=live_allowed,
            fill_price=fill_price,
        )
    raise ExecutionError("mode must be paper or live.")


def _execute_paper(
    *,
    intent: OrderIntent,
    paper_broker: Any,
    fill_price: Decimal,
) -> ExecutionResult:
    if intent.quantity is None:
        raise ExecutionError("Paper execution requires quantity.")

    price = Decimal(intent.price) if intent.order_type == "LIMIT" and intent.price else fill_price
    result = paper_broker.execute_order(
        symbol=intent.symbol,
        side=intent.side,
        currency=intent.currency,
        quantity=intent.quantity,
        fill_price=_decimal_text(price),
        client_order_id=intent.client_order_id,
    )
    return ExecutionResult(
        mode="paper",
        status="FILLED",
        result=result,
        notional=_decimal_text(Decimal(intent.quantity) * price),
    )


def _execute_live(
    *,
    intent: OrderIntent,
    live_client: Any,
    account_seq: int | str | None,
    live_allowed: bool,
    fill_price: Decimal,
) -> ExecutionResult:
    assert_live_order_allowed(config_live_enabled=live_allowed, cli_live=True)
    if account_seq is None:
        raise OrderValidationError("Live execution requires account sequence.")

    payload = build_order_payload(
        OrderRequest(
            symbol=intent.symbol,
            side=intent.side,
            order_type=intent.order_type,
            quantity=intent.quantity,
            price=intent.price,
            order_amount=intent.order_amount,
            client_order_id=intent.client_order_id,
        )
    )
    result = live_client.create_order(account_seq=account_seq, payload=payload)
    return ExecutionResult(
        mode="live",
        status="SUBMITTED",
        result=result,
        notional=_execution_notional(intent, fill_price),
    )


def _execution_notional(intent: OrderIntent, fill_price: Decimal) -> str:
    if intent.order_amount is not None:
        return _decimal_text(Decimal(intent.order_amount))
    if intent.quantity is None:
        return "0"
    price = Decimal(intent.price) if intent.order_type == "LIMIT" and intent.price else fill_price
    return _decimal_text(Decimal(intent.quantity) * price)


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")
