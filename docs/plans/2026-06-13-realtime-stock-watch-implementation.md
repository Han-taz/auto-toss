# Realtime Stock Watch Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `watch-prices` CLI command that repeatedly fetches current stock prices through the existing Toss market-data client.

**Architecture:** Reuse `TossClient.get_prices()` for market data and keep polling behavior in CLI-level helpers so it is easy to test without network or real sleeps. Stream each snapshot as one JSON object per line.

**Tech Stack:** Python 3.12, `argparse`, `json`, `time.sleep`, existing `pytest` CLI tests.

---

### Task 1: Watch Command Tests

**Files:**
- Modify: `tests/test_cli_smoke.py`
- Modify: `tests/test_cli_commands.py`

**Step 1: Write the failing tests**

Add `watch-prices` to the parser smoke test and CLI tests for bounded polling, validation, and interrupt handling.

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_smoke.py tests/test_cli_commands.py -v`

Expected: FAIL because `watch-prices` is not registered yet.

### Task 2: Watch Command Implementation

**Files:**
- Modify: `auto_toss/cli.py`

**Step 1: Implement minimal code**

Register `watch-prices`, add positive integer and non-negative float parsers, and implement `_stream_price_snapshots()`.

**Step 2: Run focused tests**

Run: `uv run pytest tests/test_cli_smoke.py tests/test_cli_commands.py -v`

Expected: PASS.

### Task 3: Documentation And Verification

**Files:**
- Modify: `README.md`

**Step 1: Document usage**

Add examples for bounded and continuous `watch-prices` usage.

**Step 2: Run all tests**

Run: `uv run pytest`

Expected: PASS.
