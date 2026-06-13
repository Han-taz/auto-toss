import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]


def test_auto_toss_runtime_directory_is_git_ignored():
    result = subprocess.run(
        ["git", "check-ignore", ".auto_toss/"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_required_sot_and_llm_wiki_documents_exist():
    required_paths = [
        "docs/SOT/architecture.md",
        "docs/SOT/documentation-policy.md",
        "docs/llm-wiki/README.md",
        "docs/llm-wiki/work-units/2026-06-13-paper-trading.md",
        "docs/llm-wiki/dead-ends/2026-06-13-paper-trading.md",
        "docs/llm-wiki/classes/paper-broker.md",
        "docs/llm-wiki/architecture/paper-trading.md",
        "docs/llm-wiki/infra/sqlite-paper-trading.md",
    ]

    missing = [path for path in required_paths if not (PROJECT_ROOT / path).is_file()]

    assert missing == []


def test_documentation_policy_requires_fresh_docs_after_work():
    policy = (PROJECT_ROOT / "docs/SOT/documentation-policy.md").read_text()

    assert "Documentation updates are mandatory after every behavior" in policy
    assert "not complete until docs are updated" in policy


def test_auto_trading_docs_exist_and_runtime_state_is_ignored():
    required = [
        "docs/llm-wiki/work-units/2026-06-13-auto-trading-safety-core.md",
        "docs/llm-wiki/architecture/auto-trading-safety-core.md",
        "docs/llm-wiki/classes/strategy-runner.md",
        "docs/llm-wiki/classes/risk-and-preflight.md",
        "docs/llm-wiki/infra/auto-trading-audit-db.md",
        "docs/llm-wiki/dead-ends/2026-06-13-auto-trading-safety-core.md",
    ]

    missing = [path for path in required if not (PROJECT_ROOT / path).is_file()]

    assert missing == []
    assert ".auto_toss/" in (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")


def test_order_lifecycle_docs_exist():
    required = [
        "docs/llm-wiki/work-units/2026-06-13-order-lifecycle-reliability.md",
        "docs/llm-wiki/architecture/order-lifecycle-reliability.md",
        "docs/llm-wiki/classes/order-lifecycle-service.md",
        "docs/llm-wiki/classes/reconciliation.md",
        "docs/llm-wiki/dead-ends/2026-06-13-order-lifecycle-reliability.md",
    ]

    missing = [path for path in required if not (PROJECT_ROOT / path).is_file()]

    assert missing == []


def test_audit_reporting_docs_exist():
    required = [
        "docs/llm-wiki/work-units/2026-06-13-audit-reporting-cli.md",
        "docs/llm-wiki/architecture/audit-reporting-cli.md",
        "docs/llm-wiki/classes/audit-reporting.md",
        "docs/llm-wiki/dead-ends/2026-06-13-audit-reporting-cli.md",
    ]

    missing = [path for path in required if not (PROJECT_ROOT / path).is_file()]

    assert missing == []
