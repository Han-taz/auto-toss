# Source Of Truth: Documentation Policy

Documentation updates are mandatory after every behavior, architecture, infrastructure, CLI, or storage change.

Work is not complete until docs are updated, tests pass, and the final response names the verification that proves the docs are current.

## Required Updates

- Update `README.md` when user-facing commands or setup change.
- Update `docs/SOT/architecture.md` when architecture boundaries change.
- Update `docs/SOT/documentation-policy.md` when documentation rules change.
- Add or update `docs/llm-wiki/work-units/YYYY-MM-DD-*.md` for daily implementation work.
- Add or update `docs/llm-wiki/classes/*.md` when important classes or methods are added.
- Add or update `docs/llm-wiki/architecture/*.md` when a subsystem design changes.
- Add or update `docs/llm-wiki/infra/*.md` when storage, runtime files, deployment, or local infrastructure changes.
- Add `docs/llm-wiki/dead-ends/*.md` when meaningful debugging, failed approaches, or caveats should be preserved.

## Agent Completion Rule

Before an agent claims completion, it must verify:

1. Relevant tests pass.
2. SOT or llm-wiki docs reflect the final behavior.
3. Runtime/secrets files remain ignored.

If documentation is stale, the task is not complete.
