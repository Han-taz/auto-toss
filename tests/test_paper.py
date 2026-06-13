import pytest

from auto_toss.paper import PaperBroker, PaperTradingError


def test_initialize_creates_default_cash_balances(tmp_path):
    broker = PaperBroker(tmp_path / "paper.sqlite3")

    broker.initialize()

    portfolio = broker.portfolio()
    assert portfolio["cash"] == {"KRW": "10000000", "USD": "10000"}
    assert portfolio["positions"] == []
    assert portfolio["realizedPnl"] == {"KRW": "0", "USD": "0"}


def test_initialize_accepts_custom_cash_balances(tmp_path):
    broker = PaperBroker(tmp_path / "paper.sqlite3")

    broker.initialize(krw_cash="500000", usd_cash="250")

    assert broker.portfolio()["cash"] == {"KRW": "500000", "USD": "250"}


def test_buy_fill_reduces_cash_and_opens_position(tmp_path):
    broker = PaperBroker(tmp_path / "paper.sqlite3")
    broker.initialize(krw_cash="200000", usd_cash="0")

    fill = broker.execute_order(
        symbol="005930",
        side="BUY",
        currency="KRW",
        quantity="2",
        fill_price="70000",
        client_order_id="paper-1",
    )

    portfolio = broker.portfolio()
    assert fill["symbol"] == "005930"
    assert fill["side"] == "BUY"
    assert fill["amount"] == "140000"
    assert portfolio["cash"]["KRW"] == "60000"
    assert portfolio["positions"] == [
        {
            "symbol": "005930",
            "currency": "KRW",
            "quantity": "2",
            "averageCost": "70000",
            "marketValue": None,
            "unrealizedPnl": None,
        }
    ]


def test_buy_rejects_insufficient_cash(tmp_path):
    broker = PaperBroker(tmp_path / "paper.sqlite3")
    broker.initialize(krw_cash="100000", usd_cash="0")

    with pytest.raises(PaperTradingError, match="Insufficient KRW cash"):
        broker.execute_order(
            symbol="005930",
            side="BUY",
            currency="KRW",
            quantity="2",
            fill_price="70000",
        )


def test_sell_fill_updates_position_cash_and_realized_pnl(tmp_path):
    broker = PaperBroker(tmp_path / "paper.sqlite3")
    broker.initialize(krw_cash="200000", usd_cash="0")
    broker.execute_order(
        symbol="005930",
        side="BUY",
        currency="KRW",
        quantity="2",
        fill_price="70000",
    )

    fill = broker.execute_order(
        symbol="005930",
        side="SELL",
        currency="KRW",
        quantity="1",
        fill_price="80000",
    )

    portfolio = broker.portfolio(mark_prices={"005930": "81000"})
    assert fill["realizedPnl"] == "10000"
    assert portfolio["cash"]["KRW"] == "140000"
    assert portfolio["realizedPnl"] == {"KRW": "10000", "USD": "0"}
    assert portfolio["positions"] == [
        {
            "symbol": "005930",
            "currency": "KRW",
            "quantity": "1",
            "averageCost": "70000",
            "marketValue": "81000",
            "unrealizedPnl": "11000",
        }
    ]


def test_sell_rejects_insufficient_position(tmp_path):
    broker = PaperBroker(tmp_path / "paper.sqlite3")
    broker.initialize()

    with pytest.raises(PaperTradingError, match="Insufficient 005930 position"):
        broker.execute_order(
            symbol="005930",
            side="SELL",
            currency="KRW",
            quantity="1",
            fill_price="70000",
        )


def test_ledger_returns_latest_fills_first(tmp_path):
    broker = PaperBroker(tmp_path / "paper.sqlite3")
    broker.initialize(krw_cash="200000", usd_cash="0")
    broker.execute_order(symbol="005930", side="BUY", currency="KRW", quantity="1", fill_price="70000")
    broker.execute_order(symbol="005930", side="SELL", currency="KRW", quantity="1", fill_price="80000")

    ledger = broker.ledger()

    assert [fill["side"] for fill in ledger] == ["SELL", "BUY"]
