from dataclasses import dataclass
import uuid


class OrderValidationError(ValueError):
    pass


class LiveTradingNotEnabled(RuntimeError):
    pass


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str
    order_type: str
    quantity: str | None = None
    price: str | None = None
    order_amount: str | None = None
    time_in_force: str | None = None
    client_order_id: str | None = None
    confirm_high_value_order: bool = False


def build_order_payload(request: OrderRequest) -> dict[str, object]:
    side = request.side.upper()
    order_type = request.order_type.upper()

    has_quantity = request.quantity is not None
    has_order_amount = request.order_amount is not None
    if has_quantity == has_order_amount:
        raise OrderValidationError("Exactly one of quantity or orderAmount is required.")

    if has_order_amount and order_type != "MARKET":
        raise OrderValidationError("Amount-based orders must use MARKET order type.")

    payload: dict[str, object] = {
        "clientOrderId": request.client_order_id or generate_client_order_id(),
        "symbol": request.symbol,
        "side": side,
        "orderType": order_type,
    }

    if request.time_in_force:
        payload["timeInForce"] = request.time_in_force.upper()

    if has_quantity:
        payload["quantity"] = request.quantity
        if order_type == "LIMIT":
            if not request.price:
                raise OrderValidationError("LIMIT orders require price.")
            payload["price"] = request.price
        elif request.price is not None:
            raise OrderValidationError("MARKET orders must not include price.")

    if has_order_amount:
        payload["orderAmount"] = request.order_amount
        if request.price is not None:
            raise OrderValidationError("Amount-based MARKET orders must not include price.")

    if request.confirm_high_value_order:
        payload["confirmHighValueOrder"] = True

    return payload


def assert_live_order_allowed(*, config_live_enabled: bool, cli_live: bool) -> None:
    if not config_live_enabled or not cli_live:
        raise LiveTradingNotEnabled(
            "Live order placement requires TOSS_LIVE_TRADING=true and the --live flag."
        )


def generate_client_order_id() -> str:
    return uuid.uuid4().hex
