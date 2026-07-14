# Claude Code CLI Reference

## Eligibility

Claude is eligible as Developer or Reviewer. The user, plan, or launcher chooses the role, model, and effort. This reference does not rank its capability.

## Reviewer launch

Write schema-v2 policy/request JSON as documented in [reviewer-contract.md](reviewer-contract.md), then use `reviewer_jobs.py launch`. The launcher owns `claude -p`, model/effort flags, `--permission-mode plan`, output format, repository directory, prompt, and capture.

Reviewer command shape:

```text
claude -p <prompt> [--model <model>] [--effort <effort>] --permission-mode plan --output-format text --add-dir <repo>
```

Plan mode is the closest tested Reviewer configuration. It restricts direct editing behavior, but command execution may still depend on harness/model behavior. Treat its read-only boundary as partial and rely on the Reviewer prompt, Developer verification, and repository mutation gates.

## Lifecycle

Use `reviewer_jobs.py activity`, `wait`, `extract`, and `cancel`. The helper can discover Claude JSONL sessions and uses session timestamps plus assistant activity as health signals. Empty stdout while the process runs is not evidence of failure.

Do not continue a Reviewer through a raw `--resume` command. Write a new validated request with an `-rN` label.

## Authentication and configuration

Use the environment and authentication supplied by the caller. Do not redirect Claude home/configuration or invent credential variables. If an explicit model or effort is selected, the launcher passes it without capability ranking; report unsupported selections as launch failures.
