# Toss Auto Trading Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a safe Python CLI foundation for Toss Securities Open API that supports Korean and US stock market/account data, order previews, and explicitly gated live order placement.

**Architecture:** Create a small `auto_toss` package behind a CLI entrypoint. Keep configuration, OAuth token handling, HTTP request behavior, API methods, order validation, and CLI rendering separate enough to test without real Toss API calls.

**Tech Stack:** Python 3.12, `httpx`, `python-dotenv`, `pytest`, `respx`, standard-library `argparse`, `dataclasses`, and `decimal`.

---

### Task 1: Project Dependencies And Package Skeleton

**Files:**
- Modify: `pyproject.toml`
- Modify: `main.py`
- Create: `auto_toss/__init__.py`
- Create: `auto_toss/cli.py`
- Create: `tests/test_cli_smoke.py`

**Step 1: Write the failing test**

Create `tests/test_cli_smoke.py`:

```python
from auto_toss.cli import build_parser


def test_parser_has_expected_commands():
    parser = build_parser()
    commands = parser._subparsers._group_actions[0].choices

    assert {"prices", "stocks", "accounts", "holdings", "preview-order", "place-order"} <= set(commands)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_smoke.py -v`

Expected: FAIL because `pytest` or the `auto_toss` package is not available yet.

**Step 3: Write minimal implementation**

Update `pyproject.toml`:

```toml
[project]
name = "auto-toss"
version = "0.1.0"
description = "Safe Toss Securities Open API CLI foundation"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27.0",
    "python-dotenv>=1.0.1",
]

[project.scripts]
auto-toss = "auto_toss.cli:main"

[dependency-groups]
dev = [
    "pytest>=8.2.0",
    "respx>=0.21.1",
]
```

Create `auto_toss/__init__.py`:

```python
__all__ = ["__version__"]

__version__ = "0.1.0"
```

Create `auto_toss/cli.py` with `build_parser()` and placeholder command handlers.

Update `main.py`:

```python
from auto_toss.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_smoke.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add pyproject.toml main.py auto_toss/__init__.py auto_toss/cli.py tests/test_cli_smoke.py
git commit -m "feat: add cli package skeleton"
```

### Task 2: Configuration Loading

**Files:**
- Create: `auto_toss/config.py`
- Create: `.env.example`
- Create: `tests/test_config.py`

**Step 1: Write the failing tests**

Create tests covering:

```python
import pytest

from auto_toss.config import Config, ConfigError


def test_config_reads_required_credentials_without_printing_values(monkeypatch):
    monkeypatch.setenv("API_KEY", "client-id")
    monkeypatch.setenv("SECRET_KEY", "client-secret")

    config = Config.from_env()

    assert config.client_id == "client-id"
    assert config.client_secret == "client-secret"
    assert "client-secret" not in repr(config)


def test_config_requires_credentials(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ConfigError, match="API_KEY"):
        Config.from_env()


def test_live_trading_requires_exact_true(monkeypatch):
    monkeypatch.setenv("API_KEY", "client-id")
    monkeypatch.setenv("SECRET_KEY", "client-secret")
    monkeypatch.setenv("TOSS_LIVE_TRADING", "true")

    assert Config.from_env().live_trading_enabled is True
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`

Expected: FAIL because `auto_toss.config` does not exist.

**Step 3: Write minimal implementation**

Implement `Config` as a frozen dataclass. Read `.env` with `python-dotenv`. Expose `base_url`, `client_id`, `client_secret`, and `live_trading_enabled`. Make `repr=False` for secrets.

Create `.env.example`:

```dotenv
API_KEY=
SECRET_KEY=
TOSS_LIVE_TRADING=false
# TOSS_BASE_URL=https://openapi.tossinvest.com
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add auto_toss/config.py .env.example tests/test_config.py
git commit -m "feat: load toss api configuration"
```

### Task 3: Toss API Client Auth And Requests

**Files:**
- Create: `auto_toss/errors.py`
- Create: `auto_toss/client.py`
- Create: `tests/test_client_auth.py`
- Create: `tests/test_client_requests.py`

**Step 1: Write failing tests**

Cover:
- `POST /oauth2/token` sends `grant_type=client_credentials`, `client_id`, `client_secret`.
- token is reused while valid.
- `GET /api/v1/prices` sends bearer token.
- account-context requests send `X-Tossinvest-Account`.
- OAuth and Toss error envelopes raise typed exceptions.

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_client_auth.py tests/test_client_requests.py -v`

Expected: FAIL because client modules do not exist.

**Step 3: Write minimal implementation**

Implement:
- `TossApiError`
- `TossAuthError`
- `TossRateLimitError`
- `TossClient`
- `TossClient.authenticate()`
- private request helper `_request(method, path, *, params=None, json=None, account_seq=None)`

Use `httpx.Client`. Token response fields are `access_token`, `token_type`, `expires_in`. Cache token until 60 seconds before expiry.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_client_auth.py tests/test_client_requests.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add auto_toss/errors.py auto_toss/client.py tests/test_client_auth.py tests/test_client_requests.py
git commit -m "feat: add toss api client auth"
```

### Task 4: Market And Account API Methods

**Files:**
- Modify: `auto_toss/client.py`
- Create: `tests/test_client_endpoints.py`

**Step 1: Write failing tests**

Cover:
- `get_prices(["005930", "AAPL"])` calls `/api/v1/prices?symbols=005930,AAPL`.
- `get_stocks(["005930", "AAPL"])` calls `/api/v1/stocks`.
- `get_accounts()` calls `/api/v1/accounts`.
- `get_holdings(account_seq=1, symbol="AAPL")` calls `/api/v1/holdings` with account header and symbol query.
- `get_buying_power`, `get_sellable_quantity`, and `get_commissions` call the official order-info endpoints.

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_client_endpoints.py -v`

Expected: FAIL because endpoint methods do not exist.

**Step 3: Write minimal implementation**

Add endpoint methods to `TossClient`. Return decoded JSON `result` when present; return full JSON for OAuth-like responses.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_client_endpoints.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add auto_toss/client.py tests/test_client_endpoints.py
git commit -m "feat: add toss market and account endpoints"
```

### Task 5: Order Models And Safety Gate

**Files:**
- Create: `auto_toss/orders.py`
- Create: `tests/test_orders.py`

**Step 1: Write failing tests**

Cover:
- limit quantity order includes `price`.
- market quantity order omits `price`.
- US amount-based market order includes `orderAmount` and no `quantity`.
- amount-based order rejects non-market order types.
- live submission is denied unless config live trading is enabled and CLI `--live` is true.
- generated `clientOrderId` is no more than 36 chars and uses only letters, numbers, `_`, `-`.

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_orders.py -v`

Expected: FAIL because `auto_toss.orders` does not exist.

**Step 3: Write minimal implementation**

Implement:
- `OrderRequest`
- `LiveTradingNotEnabled`
- `build_order_payload()`
- `assert_live_order_allowed(config_live_enabled: bool, cli_live: bool)`
- `generate_client_order_id()`

Use string quantities/prices/amounts to preserve API decimal behavior.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_orders.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add auto_toss/orders.py tests/test_orders.py
git commit -m "feat: add order payload safety checks"
```

### Task 6: CLI Command Behavior

**Files:**
- Modify: `auto_toss/cli.py`
- Create: `tests/test_cli_commands.py`

**Step 1: Write failing tests**

Use a fake client factory and cover:
- `prices 005930 AAPL` prints JSON result.
- `accounts` prints JSON result.
- `holdings --account 1 --symbol AAPL` passes account and symbol.
- `preview-order` prints payload and never calls `create_order`.
- `place-order` without `--live` exits with a non-zero status.
- `place-order --live` calls `create_order` only when config live trading is enabled.

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_commands.py -v`

Expected: FAIL because CLI handlers are placeholders.

**Step 3: Write minimal implementation**

Implement command handlers with dependency injection for config/client in tests. Print JSON with `json.dumps(..., ensure_ascii=False, indent=2)`.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_commands.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add auto_toss/cli.py tests/test_cli_commands.py
git commit -m "feat: wire toss cli commands"
```

### Task 7: README Usage And Full Verification

**Files:**
- Modify: `README.md`

**Step 1: Write README content**

Document:
- official Toss docs used
- `.env` format
- dry-run default
- command examples
- live order two-factor software gate
- warning that this is not financial advice and live trading can lose money

**Step 2: Run full verification**

Run:

```bash
uv run pytest
uv run auto-toss --help
uv run auto-toss preview-order --symbol 005930 --side BUY --order-type LIMIT --quantity 1 --price 70000
```

Expected: all tests pass, help renders, preview prints a payload and does not submit an order.

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document toss cli usage"
```

### Task 8: Completion Audit

**Files:**
- Inspect: `docs/plans/2026-06-13-toss-auto-trading-design.md`
- Inspect: test output
- Inspect: `git status --short`

**Step 1: Audit requirements**

Confirm:
- `.env` is ignored.
- official docs are cited.
- Korean and US symbols are accepted through the same command path.
- market/account/order-info endpoints are implemented.
- order preview is implemented.
- live order requires both `TOSS_LIVE_TRADING=true` and `--live`.
- tests do not call the real Toss API.

**Step 2: Final verification**

Run:

```bash
git check-ignore -v .env
uv run pytest
git status --short
```

Expected:
- `.env` is ignored by `.gitignore`.
- tests pass.
- no accidental `.env` staging or dirty files except intentionally untracked user scaffold if left outside commits.

**Step 3: Report**

Summarize implemented files, verification commands, and any remaining limitations such as no autonomous strategy loop or websocket support.
