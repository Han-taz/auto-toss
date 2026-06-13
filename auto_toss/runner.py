from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from auto_toss.audit import AuditStore
from auto_toss.execution import execute_intent
from auto_toss.preflight import run_preflight
from auto_toss.risk import CheckResult, estimate_notional, evaluate_risk
from auto_toss.strategy import OrderIntent, load_strategy_config


@dataclass(frozen=True)
class RunResult:
    run_id: int
    status: str
    executed: int
    rejected: int
    skipped: int

    def to_dict(self) -> dict[str, object]:
        return {
            "runId": self.run_id,
            "status": self.status,
            "executed": self.executed,
            "rejected": self.rejected,
            "skipped": self.skipped,
        }


@dataclass(frozen=True)
class StrategyRunner:
    config_path: str | Path
    mode: str
    audit_store: AuditStore
    toss_client: Any
    paper_broker: Any
    live_allowed: bool
    account_seq: int | str | None = None

    def run_once(self) -> RunResult:
        config = load_strategy_config(self.config_path)
        run_id = self.audit_store.start_run(
            mode=self.mode,
            config_path=str(self.config_path),
        )
        executed = 0
        rejected = 0
        skipped = 0

        try:
            for intent in config.intents:
                intent_id = self.audit_store.record_intent(
                    run_id=run_id,
                    symbol=intent.symbol,
                    side=intent.side,
                    payload=_intent_payload(intent),
                )
                last_price = _last_price_for(
                    self.toss_client.get_prices([intent.symbol]),
                    intent.symbol,
                )
                if not intent.trigger.matches(last_price):
                    self._record_check(
                        run_id,
                        intent_id,
                        CheckResult(
                            stage="strategy",
                            name="trigger",
                            status="SKIP",
                            reason="Intent trigger did not match current price.",
                            evidence={
                                "lastPrice": _decimal_text(last_price) if last_price else None,
                                "trigger": {
                                    "kind": intent.trigger.kind,
                                    "price": (
                                        _decimal_text(intent.trigger.price)
                                        if intent.trigger.price
                                        else None
                                    ),
                                },
                            },
                        ),
                    )
                    skipped += 1
                    continue

                risk_results = evaluate_risk(
                    intent=intent,
                    risk=config.risk,
                    last_price=last_price,
                    daily_order_count=self.audit_store.daily_order_count(),
                    daily_notional=self.audit_store.daily_notional(),
                )
                self._record_checks(run_id, intent_id, risk_results)
                if _has_rejection(risk_results):
                    rejected += 1
                    continue

                notional = estimate_notional(intent, last_price)
                if notional is None:
                    rejected += 1
                    continue

                preflight_results = run_preflight(
                    client=self.toss_client,
                    intent=intent,
                    mode=self.mode,
                    account_seq=self.account_seq,
                    notional=notional,
                )
                self._record_checks(run_id, intent_id, preflight_results)
                if _has_rejection(preflight_results):
                    rejected += 1
                    continue

                execution = execute_intent(
                    intent=intent,
                    mode=self.mode,
                    paper_broker=self.paper_broker,
                    live_client=self.toss_client,
                    account_seq=self.account_seq,
                    live_allowed=self.live_allowed,
                    fill_price=_fill_price(intent, last_price),
                )
                self.audit_store.record_execution(
                    run_id=run_id,
                    intent_id=intent_id,
                    mode=execution.mode,
                    status=execution.status,
                    result=execution.result,
                    notional=execution.notional,
                )
                executed += 1

            self.audit_store.complete_run(run_id=run_id, status="COMPLETED")
            return RunResult(
                run_id=run_id,
                status="COMPLETED",
                executed=executed,
                rejected=rejected,
                skipped=skipped,
            )
        except Exception:
            self.audit_store.complete_run(run_id=run_id, status="FAILED")
            raise

    def _record_checks(
        self,
        run_id: int,
        intent_id: int,
        results: list[CheckResult],
    ) -> None:
        for result in results:
            self._record_check(run_id, intent_id, result)

    def _record_check(self, run_id: int, intent_id: int, result: CheckResult) -> None:
        self.audit_store.record_check(
            run_id=run_id,
            intent_id=intent_id,
            stage=result.stage,
            name=result.name,
            status=result.status,
            reason=result.reason,
            evidence=result.evidence,
        )


def _has_rejection(results: list[CheckResult]) -> bool:
    return any(result.status == "REJECT" for result in results)


def _last_price_for(payload: Any, symbol: str) -> Decimal | None:
    if isinstance(payload, dict):
        if symbol in payload:
            return _parse_decimal(payload[symbol])
        for key in ("lastPrice", "price", "currentPrice", "close"):
            if key in payload:
                return _parse_decimal(payload[key])
        for value in payload.values():
            parsed = _last_price_for(value, symbol)
            if parsed is not None:
                return parsed
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict) and item.get("symbol") == symbol:
                for key in ("lastPrice", "price", "currentPrice", "close"):
                    if key in item:
                        return _parse_decimal(item[key])
        for item in payload:
            parsed = _last_price_for(item, symbol)
            if parsed is not None:
                return parsed
    return None


def _fill_price(intent: OrderIntent, last_price: Decimal | None) -> Decimal:
    if intent.order_type == "LIMIT" and intent.price is not None:
        return Decimal(intent.price)
    if last_price is None:
        raise RuntimeError("Market execution requires last price.")
    return last_price


def _intent_payload(intent: OrderIntent) -> dict[str, object]:
    return {
        "symbol": intent.symbol,
        "side": intent.side,
        "currency": intent.currency,
        "orderType": intent.order_type,
        "quantity": intent.quantity,
        "price": intent.price,
        "orderAmount": intent.order_amount,
        "clientOrderId": intent.client_order_id,
        "trigger": {
            "kind": intent.trigger.kind,
            "price": _decimal_text(intent.trigger.price) if intent.trigger.price else None,
        },
    }


def _parse_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed > 0 else None


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")
