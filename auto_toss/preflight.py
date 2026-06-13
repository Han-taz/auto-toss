from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any

from auto_toss.risk import CheckResult
from auto_toss.strategy import OrderIntent


def infer_market(symbol: str) -> str:
    return "KR" if re.fullmatch(r"\d{6}", symbol) else "US"


def run_preflight(
    *,
    client: Any,
    intent: OrderIntent,
    mode: str,
    account_seq: int | str | None,
    notional: Decimal,
) -> list[CheckResult]:
    results = [
        _stock_warnings_result(client.get_stock_warnings(intent.symbol)),
    ]

    if intent.order_type == "LIMIT":
        results.append(_price_limits_result(client.get_price_limits(intent.symbol), intent))

    if mode != "live":
        return results

    results.append(_market_calendar_result(client.get_market_calendar(infer_market(intent.symbol))))
    if account_seq is None:
        results.append(
            _reject(
                "account_required",
                "Live preflight requires an account sequence.",
                {},
            )
        )
        return results

    if intent.side == "BUY":
        results.append(
            _buying_power_result(
                client.get_buying_power(account_seq=account_seq, currency=intent.currency),
                notional,
            )
        )
    if intent.side == "SELL":
        results.append(
            _sellable_quantity_result(
                client.get_sellable_quantity(account_seq=account_seq, symbol=intent.symbol),
                intent,
            )
        )

    results.append(
        _open_orders_result(
            client.get_orders(account_seq=account_seq, status="OPEN", symbol=intent.symbol),
            intent,
        )
    )
    return results


def _stock_warnings_result(payload: Any) -> CheckResult:
    warnings = _as_list(payload)
    if warnings:
        return _reject(
            "stock_warnings",
            "Active stock warnings exist.",
            {"warnings": warnings},
        )
    return _pass("stock_warnings", "No active stock warnings.", {})


def _price_limits_result(payload: Any, intent: OrderIntent) -> CheckResult:
    price = _parse_decimal(intent.price)
    lower = _find_decimal(payload, ("lowerLimitPrice", "lowerPrice", "lowerLimit", "minPrice"))
    upper = _find_decimal(payload, ("upperLimitPrice", "upperPrice", "upperLimit", "maxPrice"))
    evidence = {
        "price": _decimal_text(price) if price is not None else None,
        "lower": _decimal_text(lower) if lower is not None else None,
        "upper": _decimal_text(upper) if upper is not None else None,
    }
    if price is None or lower is None or upper is None:
        return _reject(
            "price_limits",
            "Limit order price bounds could not be verified.",
            evidence,
        )
    if price < lower or price > upper:
        return _reject("price_limits", "Limit order price is outside allowed bounds.", evidence)
    return _pass("price_limits", "Limit order price is within allowed bounds.", evidence)


def _market_calendar_result(payload: Any) -> CheckResult:
    if _contains_open_status(payload):
        return _pass("market_calendar", "Market calendar indicates an open session.", {})
    return _reject(
        "market_calendar",
        "Market calendar does not clearly indicate an open session.",
        {"calendar": payload},
    )


def _buying_power_result(payload: Any, notional: Decimal) -> CheckResult:
    available = _find_decimal(
        payload,
        ("availableAmount", "buyingPower", "availableCash", "amount"),
    )
    evidence = {
        "available": _decimal_text(available) if available is not None else None,
        "notional": _decimal_text(notional),
    }
    if available is None:
        return _reject("buying_power", "Buying power could not be verified.", evidence)
    if available < notional:
        return _reject("buying_power", "Buying power is below order notional.", evidence)
    return _pass("buying_power", "Buying power covers order notional.", evidence)


def _sellable_quantity_result(payload: Any, intent: OrderIntent) -> CheckResult:
    sellable = _find_decimal(payload, ("sellableQuantity", "quantity", "availableQuantity"))
    quantity = _parse_decimal(intent.quantity)
    evidence = {
        "sellableQuantity": _decimal_text(sellable) if sellable is not None else None,
        "orderQuantity": _decimal_text(quantity) if quantity is not None else None,
    }
    if sellable is None or quantity is None:
        return _reject("sellable_quantity", "Sellable quantity could not be verified.", evidence)
    if sellable < quantity:
        return _reject("sellable_quantity", "Sellable quantity is below order quantity.", evidence)
    return _pass("sellable_quantity", "Sellable quantity covers order quantity.", evidence)


def _open_orders_result(payload: Any, intent: OrderIntent) -> CheckResult:
    opposite_side = "SELL" if intent.side == "BUY" else "BUY"
    orders = _as_list(payload)
    opposite_orders = [
        order
        for order in orders
        if isinstance(order, dict) and str(order.get("side", "")).upper() == opposite_side
    ]
    if opposite_orders:
        return _reject(
            "opposite_open_orders",
            "Opposite open orders exist for this symbol.",
            {"orders": opposite_orders},
        )
    return _pass("opposite_open_orders", "No opposite open orders found.", {})


def _as_list(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("orders", "items", "warnings", "result"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return []
    return []


def _contains_open_status(payload: Any) -> bool:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.lower().endswith("status") and isinstance(value, str) and "OPEN" in value.upper():
                return True
            if _contains_open_status(value):
                return True
    if isinstance(payload, list):
        return any(_contains_open_status(item) for item in payload)
    return False


def _find_decimal(payload: Any, keys: tuple[str, ...]) -> Decimal | None:
    if isinstance(payload, dict):
        for key in keys:
            if key in payload:
                parsed = _parse_decimal(payload[key])
                if parsed is not None:
                    return parsed
        for value in payload.values():
            parsed = _find_decimal(value, keys)
            if parsed is not None:
                return parsed
    if isinstance(payload, list):
        for item in payload:
            parsed = _find_decimal(item, keys)
            if parsed is not None:
                return parsed
    return None


def _parse_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _pass(name: str, reason: str, evidence: dict[str, object]) -> CheckResult:
    return CheckResult(
        stage="preflight",
        name=name,
        status="PASS",
        reason=reason,
        evidence=evidence,
    )


def _reject(name: str, reason: str, evidence: dict[str, object]) -> CheckResult:
    return CheckResult(
        stage="preflight",
        name=name,
        status="REJECT",
        reason=reason,
        evidence=evidence,
    )


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")
