import httpx
import pytest
import respx

from auto_toss.client import TossClient
from auto_toss.config import Config
from auto_toss.errors import TossApiError, TossRateLimitError


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
def test_request_sends_bearer_token():
    mock_token()
    prices_route = respx.get("https://toss.example.test/api/v1/prices").mock(
        return_value=httpx.Response(200, json={"result": [{"symbol": "005930"}]})
    )

    result = TossClient(make_config())._request(
        "GET",
        "/api/v1/prices",
        params={"symbols": "005930"},
    )

    assert result == {"result": [{"symbol": "005930"}]}
    assert prices_route.calls[0].request.headers["Authorization"] == "Bearer token-1"


@respx.mock
def test_request_sends_account_header_for_account_context():
    mock_token()
    holdings_route = respx.get("https://toss.example.test/api/v1/holdings").mock(
        return_value=httpx.Response(200, json={"result": {"items": []}})
    )

    TossClient(make_config())._request("GET", "/api/v1/holdings", account_seq=7)

    assert holdings_route.calls[0].request.headers["X-Tossinvest-Account"] == "7"


@respx.mock
def test_request_raises_toss_api_error_envelope():
    mock_token()
    respx.get("https://toss.example.test/api/v1/prices").mock(
        return_value=httpx.Response(
            400,
            json={
                "error": {
                    "requestId": "request-1",
                    "code": "invalid-request",
                    "message": "bad symbols",
                    "data": {"field": "symbols"},
                }
            },
        )
    )

    with pytest.raises(TossApiError) as exc_info:
        TossClient(make_config())._request("GET", "/api/v1/prices")

    assert exc_info.value.code == "invalid-request"
    assert exc_info.value.request_id == "request-1"
    assert exc_info.value.data == {"field": "symbols"}


@respx.mock
def test_request_raises_rate_limit_error_with_retry_headers():
    mock_token()
    respx.get("https://toss.example.test/api/v1/prices").mock(
        return_value=httpx.Response(
            429,
            headers={
                "Retry-After": "2",
                "X-RateLimit-Limit": "10",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "1",
            },
            json={
                "error": {
                    "requestId": "request-2",
                    "code": "rate-limit-exceeded",
                    "message": "too many requests",
                }
            },
        )
    )

    with pytest.raises(TossRateLimitError) as exc_info:
        TossClient(make_config())._request("GET", "/api/v1/prices")

    assert exc_info.value.retry_after == "2"
    assert exc_info.value.rate_limit == "10"
