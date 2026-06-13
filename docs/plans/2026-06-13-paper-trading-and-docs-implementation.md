# Paper Trading And Docs System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add local SQLite paper trading and a persistent documentation system for future agent handoff.

**Architecture:** Keep paper trading separate from Toss live order placement. Add a local broker/storage module backed by SQLite, wire it into CLI commands, and update SOT/wiki docs as a mandatory completion artifact.

**Tech Stack:** Python 3.12, standard-library `sqlite3`, `decimal`, `dataclasses`, `argparse`, existing pytest suite.

---

### Task 1: Ignore Runtime Paper Trading State

**Files:**
- Modify: `.gitignore`
- Test: `tests/test_docs_and_runtime.py`

**Step 1: Write failing test**

Assert `git check-ignore .auto_toss/` succeeds.

**Step 2: Run test**

Run: `uv run pytest tests/test_docs_and_runtime.py -v`

Expected: FAIL because `.auto_toss/` is not ignored yet.

**Step 3: Implement**

Add `.auto_toss/` to `.gitignore`.

**Step 4: Verify**

Run: `uv run pytest tests/test_docs_and_runtime.py -v`

Expected: PASS.

### Task 2: Paper Trading Storage And Broker

**Files:**
- Create: `auto_toss/paper.py`
- Test: `tests/test_paper.py`

**Step 1: Write failing tests**

Cover init defaults, custom cash, BUY fill, SELL fill with realized P&L, insufficient cash, and insufficient quantity.

**Step 2: Run tests**

Run: `uv run pytest tests/test_paper.py -v`

Expected: FAIL because `auto_toss.paper` does not exist.

**Step 3: Implement**

Create:

- `PaperTradingError`
- `PaperBroker`
- `PaperBroker.initialize(reset=False, krw_cash="10000000", usd_cash="10000")`
- `PaperBroker.execute_order(symbol, side, currency, quantity, fill_price, client_order_id=None)`
- `PaperBroker.portfolio(mark_prices=None)`
- `PaperBroker.ledger(limit=50)`

Use decimal strings in SQLite and `Decimal` for arithmetic.

**Step 4: Verify**

Run: `uv run pytest tests/test_paper.py -v`

Expected: PASS.

### Task 3: Paper Trading CLI

**Files:**
- Modify: `auto_toss/cli.py`
- Test: `tests/test_cli_paper.py`
- Modify: `tests/test_cli_smoke.py`

**Step 1: Write failing tests**

Cover parser commands and CLI behavior for `paper-init`, `paper-order`, `paper-portfolio`, and `paper-ledger`.

**Step 2: Run tests**

Run: `uv run pytest tests/test_cli_paper.py tests/test_cli_smoke.py -v`

Expected: FAIL because commands are not registered.

**Step 3: Implement**

Wire paper commands through dependency-injectable `paper_broker_factory`.

**Step 4: Verify**

Run: `uv run pytest tests/test_cli_paper.py tests/test_cli_smoke.py -v`

Expected: PASS.

### Task 4: Documentation System

**Files:**
- Create: `docs/SOT/architecture.md`
- Create: `docs/SOT/documentation-policy.md`
- Create: `docs/llm-wiki/README.md`
- Create: `docs/llm-wiki/work-units/2026-06-13-paper-trading.md`
- Create: `docs/llm-wiki/dead-ends/2026-06-13-paper-trading.md`
- Create: `docs/llm-wiki/classes/paper-broker.md`
- Create: `docs/llm-wiki/architecture/paper-trading.md`
- Create: `docs/llm-wiki/infra/sqlite-paper-trading.md`
- Modify: `README.md`
- Test: `tests/test_docs_and_runtime.py`

**Step 1: Write failing docs tests**

Assert all required docs paths exist and documentation policy mentions mandatory updates after work.

**Step 2: Run tests**

Run: `uv run pytest tests/test_docs_and_runtime.py -v`

Expected: FAIL until docs exist.

**Step 3: Implement docs**

Add the SOT and wiki documents.

**Step 4: Verify**

Run: `uv run pytest tests/test_docs_and_runtime.py -v`

Expected: PASS.

### Task 5: Full Verification

**Files:**
- Inspect: `README.md`
- Inspect: `docs/SOT/documentation-policy.md`
- Inspect: `docs/llm-wiki/work-units/2026-06-13-paper-trading.md`

**Step 1: Run full test suite**

Run: `uv run pytest`

Expected: PASS.

**Step 2: Run CLI smoke commands**

Run:

```bash
uv run auto-toss paper-init --reset --db-path /tmp/auto-toss-paper.sqlite3
uv run auto-toss paper-order --db-path /tmp/auto-toss-paper.sqlite3 --symbol 005930 --side BUY --currency KRW --quantity 1 --fill-price 70000
uv run auto-toss paper-portfolio --db-path /tmp/auto-toss-paper.sqlite3
uv run auto-toss paper-ledger --db-path /tmp/auto-toss-paper.sqlite3
```

Expected: all commands exit 0 and print JSON.

**Step 3: Audit documentation freshness**

Confirm docs mention the implemented commands, storage location, and mandatory docs update rule.
