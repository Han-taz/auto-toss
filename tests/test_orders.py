import re

import pytest

from auto_toss.orders import (
    LiveTradingNotEnabled,
    OrderRequest,
    OrderValidationError,
    assert_live_order_allowed,
    build_order_payload,
    generate_client_order_id,
)


def test_limit_quantity_order_includes_price():
    payload = build_order_payload(
        OrderRequest(
            symbol="005930",
            side="BUY",
            order_type="LIMIT",
            quantity="1",
            price="70000",
        )
    )

    assert payload["symbol"] == "005930"
    assert payload["side"] == "BUY"
    assert payload["orderType"] == "LIMIT"
    assert payload["quantity"] == "1"
    assert payload["price"] == "70000"


def test_market_quantity_order_omits_price():
    payload = build_order_payload(
        OrderRequest(
            symbol="AAPL",
            side="BUY",
            order_type="MARKET",
            quantity="1",
        )
    )

    assert payload["orderType"] == "MARKET"
    assert payload["quantity"] == "1"
    assert "price" not in payload


def test_us_amount_based_market_order_uses_order_amount_without_quantity():
    payload = build_order_payload(
        OrderRequest(
            symbol="AAPL",
            side="BUY",
            order_type="MARKET",
            order_amount="100.50",
        )
    )

    assert payload["symbol"] == "AAPL"
    assert payload["orderType"] == "MARKET"
    assert payload["orderAmount"] == "100.50"
    assert "quantity" not in payload


def test_amount_based_order_rejects_non_market_order_type():
    with pytest.raises(OrderValidationError, match="MARKET"):
        build_order_payload(
            OrderRequest(
                symbol="AAPL",
                side="BUY",
                order_type="LIMIT",
                order_amount="100.50",
                price="180.00",
            )
        )


@pytest.mark.parametrize(
    ("config_live_enabled", "cli_live"),
    [(False, False), (False, True), (True, False)],
)
def test_live_submission_requires_config_and_cli_opt_in(config_live_enabled, cli_live):
    with pytest.raises(LiveTradingNotEnabled):
        assert_live_order_allowed(config_live_enabled=config_live_enabled, cli_live=cli_live)


def test_live_submission_allowed_when_both_gates_are_enabled():
    assert_live_order_allowed(config_live_enabled=True, cli_live=True)


def test_generated_client_order_id_matches_toss_constraints():
    client_order_id = generate_client_order_id()

    assert len(client_order_id) <= 36
    assert re.fullmatch(r"[a-zA-Z0-9\-_]+", client_order_id)
