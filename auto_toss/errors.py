from typing import Any


class TossApiError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        request_id: str | None = None,
        data: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.request_id = request_id
        self.data = data
        self.status_code = status_code


class TossAuthError(TossApiError):
    pass


class TossRateLimitError(TossApiError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        request_id: str | None = None,
        data: dict[str, Any] | None = None,
        status_code: int | None = None,
        retry_after: str | None = None,
        rate_limit: str | None = None,
        rate_limit_remaining: str | None = None,
        rate_limit_reset: str | None = None,
    ) -> None:
        super().__init__(
            code,
            message,
            request_id=request_id,
            data=data,
            status_code=status_code,
        )
        self.retry_after = retry_after
        self.rate_limit = rate_limit
        self.rate_limit_remaining = rate_limit_remaining
        self.rate_limit_reset = rate_limit_reset
