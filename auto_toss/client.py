from __future__ import annotations

import time
from typing import Any

import httpx

from auto_toss.config import Config
from auto_toss.errors import TossApiError, TossAuthError, TossRateLimitError


class TossClient:
    def __init__(self, config: Config, *, http_client: httpx.Client | None = None) -> None:
        self.config = config
        self._client = http_client or httpx.Client(base_url=config.base_url, timeout=10.0)
        self._access_token: str | None = None
        self._token_expires_at = 0.0

    def authenticate(self) -> str:
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        response = self._client.post(
            "/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if response.status_code >= 400:
            payload = _safe_json(response)
            raise TossAuthError(
                payload.get("error", "auth-error"),
                payload.get("error_description", response.text),
                status_code=response.status_code,
            )

        payload = response.json()
        self._access_token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 0))
        self._token_expires_at = time.time() + max(expires_in - 60, 0)
        return self._access_token

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        account_seq: int | str | None = None,
    ) -> dict[str, Any]:
        token = self.authenticate()
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }
        if account_seq is not None:
            headers["X-Tossinvest-Account"] = str(account_seq)

        response = self._client.request(
            method,
            path,
            params=params,
            json=json,
            headers=headers,
        )
        if response.status_code >= 400:
            self._raise_api_error(response)
        return response.json()

    def get_prices(self, symbols: list[str]) -> Any:
        return _result(self._request("GET", "/api/v1/prices", params={"symbols": ",".join(symbols)}))

    def get_stocks(self, symbols: list[str]) -> Any:
        return _result(self._request("GET", "/api/v1/stocks", params={"symbols": ",".join(symbols)}))

    def get_accounts(self) -> Any:
        return _result(self._request("GET", "/api/v1/accounts"))

    def get_holdings(self, *, account_seq: int | str, symbol: str | None = None) -> Any:
        params = {"symbol": symbol} if symbol else None
        return _result(self._request("GET", "/api/v1/holdings", params=params, account_seq=account_seq))

    def get_buying_power(self, *, account_seq: int | str, currency: str) -> Any:
        return _result(
            self._request(
                "GET",
                "/api/v1/buying-power",
                params={"currency": currency},
                account_seq=account_seq,
            )
        )

    def get_sellable_quantity(self, *, account_seq: int | str, symbol: str) -> Any:
        return _result(
            self._request(
                "GET",
                "/api/v1/sellable-quantity",
                params={"symbol": symbol},
                account_seq=account_seq,
            )
        )

    def get_commissions(self, *, account_seq: int | str) -> Any:
        return _result(self._request("GET", "/api/v1/commissions", account_seq=account_seq))

    def _raise_api_error(self, response: httpx.Response) -> None:
        payload = _safe_json(response)
        error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
        code = error.get("code", f"http-{response.status_code}")
        message = error.get("message", response.text)
        request_id = error.get("requestId") or response.headers.get("X-Request-Id")
        data = error.get("data")

        if response.status_code == 429:
            raise TossRateLimitError(
                code,
                message,
                request_id=request_id,
                data=data,
                status_code=response.status_code,
                retry_after=response.headers.get("Retry-After"),
                rate_limit=response.headers.get("X-RateLimit-Limit"),
                rate_limit_remaining=response.headers.get("X-RateLimit-Remaining"),
                rate_limit_reset=response.headers.get("X-RateLimit-Reset"),
            )

        raise TossApiError(
            code,
            message,
            request_id=request_id,
            data=data,
            status_code=response.status_code,
        )


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _result(payload: dict[str, Any]) -> Any:
    return payload.get("result", payload)
