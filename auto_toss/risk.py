from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from auto_toss.strategy import OrderIntent, RiskConfig


@dataclass(frozen=True)
class CheckResult:
    stage: str
    name: str
    status: str
    reason: str
    evidence: dict[str, object]

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


def estimate_notional(intent: OrderIntent, last_price: Decimal | None) -> Decimal | None:
    if intent.order_amount is not None:
        return _parse_positive_decimal(intent.order_amount)

    quantity = _parse_positive_decimal(intent.quantity)
    if quantity is None:
        return None

    if intent.order_type == "LIMIT":
        price = _parse_positive_decimal(intent.price)
        if price is None:
            return None
        return quantity * price

    if intent.order_type == "MARKET" and last_price is not None and last_price > 0:
        return quantity * last_price

    return None


def evaluate_risk(
    *,
    intent: OrderIntent,
    risk: RiskConfig,
    last_price: Decimal | None,
    daily_order_count: int,
    daily_notional: Decimal,
) -> list[CheckResult]:
    results = [
        _kill_switch_result(risk),
        _allowed_symbol_result(intent, risk),
        _positive_values_result(intent),
    ]

    notional = estimate_notional(intent, last_price)
    if notional is None:
        results.append(
            _reject(
                "estimated_notional",
                "Order notional could not be estimated.",
                {"symbol": intent.symbol, "orderType": intent.order_type},
            )
        )
        return results

    results.append(
        _pass(
            "estimated_notional",
            "Order notional estimated.",
            {"notional": _decimal_text(notional)},
        )
    )

    results.append(
        _check_threshold(
            name="max_order_amount",
            value=notional,
            limit=risk.max_order_amount,
            reason_ok="Order notional is within per-order risk limit.",
            reason_reject="Order notional exceeds per-order risk limit.",
        )
    )
    results.append(
        _check_count(
            daily_order_count=daily_order_count,
            max_daily_orders=risk.max_daily_orders,
        )
    )
    results.append(
        _check_threshold(
            name="max_daily_notional",
            value=daily_notional + notional,
            limit=risk.max_daily_notional,
            reason_ok="Projected daily notional is within limit.",
            reason_reject="Projected daily notional exceeds limit.",
        )
    )
    return results


def _kill_switch_result(risk: RiskConfig) -> CheckResult:
    if risk.kill_switch_file and Path(risk.kill_switch_file).exists():
        return _reject(
            "kill_switch",
            "Kill switch file exists.",
            {"killSwitchFile": risk.kill_switch_file},
        )
    return _pass(
        "kill_switch",
        "Kill switch is not active.",
        {"killSwitchFile": risk.kill_switch_file},
    )


def _allowed_symbol_result(intent: OrderIntent, risk: RiskConfig) -> CheckResult:
    if intent.symbol not in risk.allowed_symbols:
        return _reject(
            "allowed_symbol",
            "Symbol is not allowed by risk config.",
            {"symbol": intent.symbol, "allowedSymbols": list(risk.allowed_symbols)},
        )
    return _pass(
        "allowed_symbol",
        "Symbol is allowed by risk config.",
        {"symbol": intent.symbol},
    )


def _positive_values_result(intent: OrderIntent) -> CheckResult:
    fields = {
        "quantity": intent.quantity,
        "price": intent.price,
        "orderAmount": intent.order_amount,
    }
    invalid = [
        name
        for name, value in fields.items()
        if value is not None and _parse_positive_decimal(value) is None
    ]
    if invalid:
        return _reject(
            "positive_values",
            "Order quantity, price, and amount values must be positive decimals.",
            {"invalidFields": invalid},
        )
    return _pass(
        "positive_values",
        "Order quantity, price, and amount values are positive when present.",
        {},
    )


def _check_threshold(
    *,
    name: str,
    value: Decimal,
    limit: Decimal,
    reason_ok: str,
    reason_reject: str,
) -> CheckResult:
    evidence = {"value": _decimal_text(value), "limit": _decimal_text(limit)}
    if value > limit:
        return _reject(name, reason_reject, evidence)
    return _pass(name, reason_ok, evidence)


def _check_count(*, daily_order_count: int, max_daily_orders: int) -> CheckResult:
    evidence = {"dailyOrderCount": daily_order_count, "maxDailyOrders": max_daily_orders}
    if daily_order_count >= max_daily_orders:
        return _reject("max_daily_orders", "Daily order count limit has been reached.", evidence)
    return _pass("max_daily_orders", "Daily order count is within limit.", evidence)


def _pass(name: str, reason: str, evidence: dict[str, object]) -> CheckResult:
    return CheckResult(
        stage="risk",
        name=name,
        status="PASS",
        reason=reason,
        evidence=evidence,
    )


def _reject(name: str, reason: str, evidence: dict[str, object]) -> CheckResult:
    return CheckResult(
        stage="risk",
        name=name,
        status="REJECT",
        reason=reason,
        evidence=evidence,
    )


def _parse_positive_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")
