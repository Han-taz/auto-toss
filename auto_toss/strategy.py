from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
import tomllib


class StrategyConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class RiskConfig:
    max_order_amount: Decimal
    max_daily_notional: Decimal
    max_daily_orders: int
    allowed_symbols: tuple[str, ...]
    kill_switch_file: str | None = None


@dataclass(frozen=True)
class Trigger:
    kind: str = "always"
    price: Decimal | None = None

    def matches(self, last_price: Decimal | None) -> bool:
        if self.kind == "always":
            return True
        if last_price is None or self.price is None:
            return False
        if self.kind == "last_price_at_or_below":
            return last_price <= self.price
        if self.kind == "last_price_at_or_above":
            return last_price >= self.price
        raise StrategyConfigError(f"Unsupported trigger kind: {self.kind}")


@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    side: str
    currency: str
    order_type: str
    quantity: str | None = None
    price: str | None = None
    order_amount: str | None = None
    client_order_id: str | None = None
    trigger: Trigger = field(default_factory=Trigger)


@dataclass(frozen=True)
class StrategyConfig:
    risk: RiskConfig
    intents: tuple[OrderIntent, ...]


def load_strategy_config(path: str | Path) -> StrategyConfig:
    try:
        with Path(path).open("rb") as file:
            payload = tomllib.load(file)
    except tomllib.TOMLDecodeError as exc:
        raise StrategyConfigError(f"Invalid strategy TOML: {exc}") from exc

    if not isinstance(payload, dict):
        raise StrategyConfigError("Strategy config must be a TOML table.")

    risk_payload = _require_table(payload, "risk")
    intents_payload = payload.get("intents")
    if not isinstance(intents_payload, list) or not intents_payload:
        raise StrategyConfigError("Strategy config requires at least one intent.")

    return StrategyConfig(
        risk=_parse_risk(risk_payload),
        intents=tuple(_parse_intent(intent) for intent in intents_payload),
    )


def _parse_risk(payload: dict[str, Any]) -> RiskConfig:
    allowed_symbols = payload.get("allowed_symbols")
    if not isinstance(allowed_symbols, list):
        raise StrategyConfigError("risk.allowed_symbols must be a list.")

    max_daily_orders = payload.get("max_daily_orders")
    if not isinstance(max_daily_orders, int) or max_daily_orders < 0:
        raise StrategyConfigError("risk.max_daily_orders must be a non-negative integer.")

    kill_switch_file = payload.get("kill_switch_file")
    if kill_switch_file is not None and not isinstance(kill_switch_file, str):
        raise StrategyConfigError("risk.kill_switch_file must be a string.")

    return RiskConfig(
        max_order_amount=_require_decimal(payload, "max_order_amount"),
        max_daily_notional=_require_decimal(payload, "max_daily_notional"),
        max_daily_orders=max_daily_orders,
        allowed_symbols=tuple(_require_string(symbol, "risk.allowed_symbols") for symbol in allowed_symbols),
        kill_switch_file=kill_switch_file,
    )


def _parse_intent(payload: Any) -> OrderIntent:
    if not isinstance(payload, dict):
        raise StrategyConfigError("Each intent must be a table.")

    return OrderIntent(
        symbol=_require_string(payload.get("symbol"), "intent.symbol"),
        side=_require_string(payload.get("side"), "intent.side").upper(),
        currency=_require_string(payload.get("currency"), "intent.currency").upper(),
        order_type=_require_string(payload.get("order_type"), "intent.order_type").upper(),
        quantity=_optional_string(payload.get("quantity"), "intent.quantity"),
        price=_optional_string(payload.get("price"), "intent.price"),
        order_amount=_optional_string(payload.get("order_amount"), "intent.order_amount"),
        client_order_id=_optional_string(payload.get("client_order_id"), "intent.client_order_id"),
        trigger=_parse_trigger(payload.get("trigger", {})),
    )


def _parse_trigger(payload: Any) -> Trigger:
    if not isinstance(payload, dict):
        raise StrategyConfigError("intent.trigger must be a table.")

    kind = payload.get("kind", "always")
    kind = _require_string(kind, "intent.trigger.kind")
    if kind not in {"always", "last_price_at_or_below", "last_price_at_or_above"}:
        raise StrategyConfigError(f"Unsupported trigger kind: {kind}")

    price = payload.get("price")
    if kind == "always":
        return Trigger(kind=kind)
    if price is None:
        raise StrategyConfigError(f"intent.trigger.price is required for {kind}.")
    return Trigger(kind=kind, price=_parse_decimal(price, "intent.trigger.price"))


def _require_table(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise StrategyConfigError(f"Strategy config requires {key} table.")
    return value


def _require_decimal(payload: dict[str, Any], key: str) -> Decimal:
    if key not in payload:
        raise StrategyConfigError(f"risk.{key} is required.")
    return _parse_decimal(payload[key], f"risk.{key}")


def _parse_decimal(value: object, field_name: str) -> Decimal:
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise StrategyConfigError(f"{field_name} must be a decimal.") from exc
    if decimal < 0:
        raise StrategyConfigError(f"{field_name} must be non-negative.")
    return decimal


def _require_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise StrategyConfigError(f"{field_name} must be a non-empty string.")
    return value


def _optional_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, field_name)
