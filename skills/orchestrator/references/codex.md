# Codex CLI Reference

## Eligibility

Codex is eligible as Developer or Reviewer. The user, plan, or launcher chooses the role, model, and effort. This reference does not rank its capability.

## Reviewer launch

Write schema-v2 policy/request JSON as documented in [reviewer-contract.md](reviewer-contract.md), then use `reviewer_jobs.py launch`. The launcher owns `codex exec`, model/reasoning flags, sandbox, repository directory, prompt, and capture.

Reviewer command shape:

```text
codex exec <prompt> [-m <model>] [-c model_reasoning_effort="<effort>"] --sandbox read-only --skip-git-repo-check -C <repo>
```

The read-only sandbox is the strongest mechanical Reviewer boundary among the current profiles. This is an enforcement fact, not a suitability ranking. The same no-edit, no-mutation, no-commit, and no-redelegation prompt applies.

## Lifecycle

Use `reviewer_jobs.py activity`, `wait`, `extract`, and `cancel`. The helper discovers Codex rollout JSONL files and uses session activity and assistant output as health/extraction fallbacks. Preserve vendor transcript fields such as `role: assistant`; they are external transcript schema, not orchestrator roles.

Do not resume a Reviewer through a raw command. Write a new validated request with an `-rN` label.

## Authentication and configuration

Use the caller-supplied Codex environment and authentication. Do not redirect `CODEX_HOME` or invent credentials. Explicit model/effort values are passed through without ranking; report unsupported selections as launch failures.
