from decimal import Decimal

import pytest

from auto_toss.strategy import (
    OrderIntent,
    StrategyConfigError,
    Trigger,
    load_strategy_config,
)


def test_load_strategy_config_normalizes_risk_and_intents(tmp_path):
    path = tmp_path / "strategy.toml"
    path.write_text(
        """
        [risk]
        max_order_amount = "100000"
        max_daily_notional = "300000"
        max_daily_orders = 5
        allowed_symbols = ["005930"]
        kill_switch_file = ".auto_toss/KILL_SWITCH"

        [[intents]]
        symbol = "005930"
        side = "buy"
        currency = "krw"
        order_type = "limit"
        quantity = "1"
        price = "70000"
        client_order_id = "demo-1"
        """,
        encoding="utf-8",
    )

    config = load_strategy_config(path)

    assert config.risk.max_order_amount == Decimal("100000")
    assert config.risk.max_daily_notional == Decimal("300000")
    assert config.risk.max_daily_orders == 5
    assert config.risk.allowed_symbols == ("005930",)
    assert config.risk.kill_switch_file == ".auto_toss/KILL_SWITCH"
    assert config.intents == (
        OrderIntent(
            symbol="005930",
            side="BUY",
            currency="KRW",
            order_type="LIMIT",
            quantity="1",
            price="70000",
            client_order_id="demo-1",
            trigger=Trigger(kind="always"),
        ),
    )


def test_load_strategy_config_parses_price_trigger(tmp_path):
    path = tmp_path / "strategy.toml"
    path.write_text(
        """
        [risk]
        max_order_amount = "100000"
        max_daily_notional = "300000"
        max_daily_orders = 5
        allowed_symbols = ["AAPL"]

        [[intents]]
        symbol = "AAPL"
        side = "SELL"
        currency = "USD"
        order_type = "MARKET"
        quantity = "1"

        [intents.trigger]
        kind = "last_price_at_or_above"
        price = "200"
        """,
        encoding="utf-8",
    )

    config = load_strategy_config(path)

    assert config.intents[0].trigger == Trigger(
        kind="last_price_at_or_above",
        price=Decimal("200"),
    )


def test_trigger_evaluation_for_price_thresholds():
    below = Trigger(kind="last_price_at_or_below", price=Decimal("70500"))
    above = Trigger(kind="last_price_at_or_above", price=Decimal("70500"))

    assert Trigger(kind="always").matches(None)
    assert below.matches(Decimal("70000"))
    assert not below.matches(Decimal("71000"))
    assert above.matches(Decimal("71000"))
    assert not above.matches(Decimal("70000"))


def test_load_strategy_config_rejects_missing_risk(tmp_path):
    path = tmp_path / "strategy.toml"
    path.write_text("[[intents]]\nsymbol = '005930'\n", encoding="utf-8")

    with pytest.raises(StrategyConfigError, match="risk"):
        load_strategy_config(path)


def test_load_strategy_config_rejects_unknown_trigger(tmp_path):
    path = tmp_path / "strategy.toml"
    path.write_text(
        """
        [risk]
        max_order_amount = "100000"
        max_daily_notional = "300000"
        max_daily_orders = 5
        allowed_symbols = ["005930"]

        [[intents]]
        symbol = "005930"
        side = "BUY"
        currency = "KRW"
        order_type = "LIMIT"
        quantity = "1"
        price = "70000"

        [intents.trigger]
        kind = "not_real"
        """,
        encoding="utf-8",
    )

    with pytest.raises(StrategyConfigError, match="Unsupported trigger kind"):
        load_strategy_config(path)
