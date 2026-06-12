from urllib.parse import parse_qs

import httpx
import pytest
import respx

from auto_toss.client import TossClient
from auto_toss.config import Config
from auto_toss.errors import TossAuthError


def make_config() -> Config:
    return Config(
        client_id="client-id",
        client_secret="client-secret",
        base_url="https://toss.example.test",
    )


@respx.mock
def test_authenticate_posts_client_credentials_form():
    token_route = respx.post("https://toss.example.test/oauth2/token").mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "token-1", "token_type": "Bearer", "expires_in": 3600},
        )
    )

    token = TossClient(make_config()).authenticate()

    assert token == "token-1"
    body = parse_qs(token_route.calls[0].request.content.decode())
    assert body == {
        "grant_type": ["client_credentials"],
        "client_id": ["client-id"],
        "client_secret": ["client-secret"],
    }


@respx.mock
def test_authenticate_reuses_valid_token():
    token_route = respx.post("https://toss.example.test/oauth2/token").mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "token-1", "token_type": "Bearer", "expires_in": 3600},
        )
    )
    client = TossClient(make_config())

    assert client.authenticate() == "token-1"
    assert client.authenticate() == "token-1"

    assert token_route.call_count == 1


@respx.mock
def test_authenticate_raises_toss_auth_error_for_oauth_error():
    respx.post("https://toss.example.test/oauth2/token").mock(
        return_value=httpx.Response(
            401,
            json={
                "error": "invalid_client",
                "error_description": "Client authentication failed.",
            },
        )
    )

    with pytest.raises(TossAuthError) as exc_info:
        TossClient(make_config()).authenticate()

    assert exc_info.value.code == "invalid_client"
    assert "Client authentication failed." in str(exc_info.value)
