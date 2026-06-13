import httpx
import respx

from auto_toss.client import TossClient
from auto_toss.config import Config


def make_config() -> Config:
    return Config(
        client_id="client-id",
        client_secret="client-secret",
        base_url="https://toss.example.test",
    )


def mock_token():
    respx.post("https://toss.example.test/oauth2/token").mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "token-1", "token_type": "Bearer", "expires_in": 3600},
        )
    )


@respx.mock
def test_get_prices_joins_kr_and_us_symbols():
    mock_token()
    route = respx.get("https://toss.example.test/api/v1/prices").mock(
        return_value=httpx.Response(200, json={"result": [{"symbol": "005930"}, {"symbol": "AAPL"}]})
    )

    result = TossClient(make_config()).get_prices(["005930", "AAPL"])

    assert result == [{"symbol": "005930"}, {"symbol": "AAPL"}]
    assert route.calls[0].request.url.params["symbols"] == "005930,AAPL"


@respx.mock
def test_get_stocks_joins_kr_and_us_symbols():
    mock_token()
    route = respx.get("https://toss.example.test/api/v1/stocks").mock(
        return_value=httpx.Response(200, json={"result": [{"symbol": "005930"}, {"symbol": "AAPL"}]})
    )

    result = TossClient(make_config()).get_stocks(["005930", "AAPL"])

    assert result == [{"symbol": "005930"}, {"symbol": "AAPL"}]
    assert route.calls[0].request.url.params["symbols"] == "005930,AAPL"


@respx.mock
def test_get_accounts_returns_result():
    mock_token()
    respx.get("https://toss.example.test/api/v1/accounts").mock(
        return_value=httpx.Response(200, json={"result": [{"accountSeq": 7}]})
    )

    assert TossClient(make_config()).get_accounts() == [{"accountSeq": 7}]


@respx.mock
def test_get_holdings_sends_account_header_and_optional_symbol():
    mock_token()
    route = respx.get("https://toss.example.test/api/v1/holdings").mock(
        return_value=httpx.Response(200, json={"result": {"items": []}})
    )

    result = TossClient(make_config()).get_holdings(account_seq=7, symbol="AAPL")

    assert result == {"items": []}
    assert route.calls[0].request.headers["X-Tossinvest-Account"] == "7"
    assert route.calls[0].request.url.params["symbol"] == "AAPL"


@respx.mock
def test_order_info_methods_call_official_endpoints():
    mock_token()
    buying_power = respx.get("https://toss.example.test/api/v1/buying-power").mock(
        return_value=httpx.Response(200, json={"result": {"currency": "KRW"}})
    )
    sellable_quantity = respx.get("https://toss.example.test/api/v1/sellable-quantity").mock(
        return_value=httpx.Response(200, json={"result": {"sellableQuantity": "1"}})
    )
    commissions = respx.get("https://toss.example.test/api/v1/commissions").mock(
        return_value=httpx.Response(200, json={"result": [{"marketCountry": "KR"}]})
    )

    client = TossClient(make_config())

    assert client.get_buying_power(account_seq=7, currency="KRW") == {"currency": "KRW"}
    assert client.get_sellable_quantity(account_seq=7, symbol="005930") == {"sellableQuantity": "1"}
    assert client.get_commissions(account_seq=7) == [{"marketCountry": "KR"}]
    assert buying_power.calls[0].request.headers["X-Tossinvest-Account"] == "7"
    assert buying_power.calls[0].request.url.params["currency"] == "KRW"
    assert sellable_quantity.calls[0].request.url.params["symbol"] == "005930"
    assert commissions.calls[0].request.headers["X-Tossinvest-Account"] == "7"


@respx.mock
def test_safety_read_endpoints_use_account_header_where_required():
    mock_token()
    warnings = respx.get("https://toss.example.test/api/v1/stocks/005930/warnings").mock(
        return_value=httpx.Response(200, json={"result": []})
    )
    limits = respx.get("https://toss.example.test/api/v1/price-limits").mock(
        return_value=httpx.Response(200, json={"result": {"symbol": "005930"}})
    )
    calendar = respx.get("https://toss.example.test/api/v1/market-calendar/KR").mock(
        return_value=httpx.Response(200, json={"result": {"market": "KR"}})
    )
    orders = respx.get("https://toss.example.test/api/v1/orders").mock(
        return_value=httpx.Response(200, json={"result": {"orders": []}})
    )

    client = TossClient(make_config())

    assert client.get_stock_warnings("005930") == []
    assert client.get_price_limits("005930") == {"symbol": "005930"}
    assert client.get_market_calendar("KR") == {"market": "KR"}
    assert client.get_orders(account_seq=7, status="OPEN", symbol="005930") == {"orders": []}

    assert "X-Tossinvest-Account" not in warnings.calls[0].request.headers
    assert "X-Tossinvest-Account" not in limits.calls[0].request.headers
    assert "X-Tossinvest-Account" not in calendar.calls[0].request.headers
    assert limits.calls[0].request.url.params["symbol"] == "005930"
    assert orders.calls[0].request.headers["X-Tossinvest-Account"] == "7"
    assert orders.calls[0].request.url.params["status"] == "OPEN"
    assert orders.calls[0].request.url.params["symbol"] == "005930"


@respx.mock
def test_create_order_posts_payload_with_account_header():
    mock_token()
    route = respx.post("https://toss.example.test/api/v1/orders").mock(
        return_value=httpx.Response(
            200,
            json={"result": {"orderId": "order-1", "clientOrderId": "client-1"}},
        )
    )
    payload = {
        "clientOrderId": "client-1",
        "symbol": "005930",
        "side": "BUY",
        "orderType": "LIMIT",
        "quantity": "1",
        "price": "70000",
    }

    result = TossClient(make_config()).create_order(account_seq=7, payload=payload)

    assert result == {"orderId": "order-1", "clientOrderId": "client-1"}
    assert route.calls[0].request.headers["X-Tossinvest-Account"] == "7"
    assert route.calls[0].request.read() == (
        b'{"clientOrderId":"client-1","symbol":"005930","side":"BUY",'
        b'"orderType":"LIMIT","quantity":"1","price":"70000"}'
    )
