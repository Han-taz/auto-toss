from decimal import Decimal

from auto_toss.risk import evaluate_risk, estimate_notional
from auto_toss.strategy import OrderIntent, RiskConfig


def make_risk(**overrides):
    values = {
        "max_order_amount": Decimal("100000"),
        "max_daily_notional": Decimal("300000"),
        "max_daily_orders": 5,
        "allowed_symbols": ("005930",),
        "kill_switch_file": None,
    }
    values.update(overrides)
    return RiskConfig(**values)


def test_risk_rejects_kill_switch_and_disallowed_symbol(tmp_path):
    kill = tmp_path / "KILL_SWITCH"
    kill.write_text("stop", encoding="utf-8")
    risk = make_risk(allowed_symbols=("AAPL",), kill_switch_file=str(kill))
    intent = OrderIntent(
        symbol="005930",
        side="BUY",
        currency="KRW",
        order_type="LIMIT",
        quantity="1",
        price="70000",
    )

    results = evaluate_risk(
        intent=intent,
        risk=risk,
        last_price=Decimal("70000"),
        daily_order_count=0,
        daily_notional=Decimal("0"),
    )

    rejected = {result.name for result in results if result.status == "REJECT"}
    assert {"kill_switch", "allowed_symbol"} <= rejected


def test_risk_rejects_order_amount_and_daily_limits():
    risk = make_risk(
        max_order_amount=Decimal("1000"),
        max_daily_notional=Decimal("2000"),
        max_daily_orders=1,
    )
    intent = OrderIntent(
        symbol="005930",
        side="BUY",
        currency="KRW",
        order_type="LIMIT",
        quantity="1",
        price="1500",
    )

    results = evaluate_risk(
        intent=intent,
        risk=risk,
        last_price=Decimal("1500"),
        daily_order_count=1,
        daily_notional=Decimal("1000"),
    )

    rejected = {result.name for result in results if result.status == "REJECT"}
    assert {"max_order_amount", "max_daily_orders", "max_daily_notional"} <= rejected


def test_risk_passes_safe_limit_order():
    risk = make_risk()
    intent = OrderIntent(
        symbol="005930",
        side="BUY",
        currency="KRW",
        order_type="LIMIT",
        quantity="1",
        price="70000",
    )

    results = evaluate_risk(
        intent=intent,
        risk=risk,
        last_price=Decimal("70000"),
        daily_order_count=0,
        daily_notional=Decimal("0"),
    )

    assert all(result.passed for result in results)


def test_estimate_notional_for_limit_market_and_amount_orders():
    assert estimate_notional(
        OrderIntent(
            symbol="005930",
            side="BUY",
            currency="KRW",
            order_type="LIMIT",
            quantity="2",
            price="70000",
        ),
        last_price=None,
    ) == Decimal("140000")
    assert estimate_notional(
        OrderIntent(
            symbol="AAPL",
            side="BUY",
            currency="USD",
            order_type="MARKET",
            quantity="2",
        ),
        last_price=Decimal("200"),
    ) == Decimal("400")
    assert estimate_notional(
        OrderIntent(
            symbol="AAPL",
            side="BUY",
            currency="USD",
            order_type="MARKET",
            order_amount="100.50",
        ),
        last_price=None,
    ) == Decimal("100.50")


def test_risk_rejects_unestimated_notional():
    risk = make_risk()
    intent = OrderIntent(
        symbol="005930",
        side="BUY",
        currency="KRW",
        order_type="MARKET",
        quantity="1",
    )

    results = evaluate_risk(
        intent=intent,
        risk=risk,
        last_price=None,
        daily_order_count=0,
        daily_notional=Decimal("0"),
    )

    assert any(
        result.name == "estimated_notional" and result.status == "REJECT"
        for result in results
    )
