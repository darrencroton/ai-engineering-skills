# Qwen Code CLI Reference

## Role and command

Qwen Code is eligible as Developer or Reviewer. The user, plan, or launcher chooses the role, model, and effort. This reference does not rank its capability.

Write schema-v2 policy/request JSON as documented in [reviewer-contract.md](reviewer-contract.md), then use `reviewer_jobs.py launch`. The launcher owns Qwen's headless prompt, model flag, sandbox, text output, repository working directory, and capture. The tested Qwen Code command has no effort/variant flag, so a non-default effort request fails closed before launch.

```bash
qwen --prompt <prompt> [--model <model>] --sandbox --output-format text
```

The tracked launcher fixes the child working directory to the policy repository; Qwen Code has no separate repository-directory flag.

## Read-only boundary

The launcher requests `--sandbox`, which isolates Qwen Code from the host when enabled. A caller-supplied `QWEN_SANDBOX` setting can override that flag, so the evidence profile records sandboxing as requested rather than guaranteed. On macOS, the default Seatbelt profile restricts writes outside the project directory; container providers mount the workspace. Neither mechanism makes the repository itself read-only. The embedded Reviewer contract therefore remains the authority that forbids edits, mutation-prone commands, Git/GitHub mutations, commits, and re-delegation. This profile is prompt-enforced, not mechanically read-only.

## Lifecycle and configuration

Qwen Code has no dedicated session-log integration in the helper. `activity` uses helper-managed file/process signals. Use `wait`, `extract`, and `cancel` normally. Do not resume through a raw command; write a new validated request with an `-rN` label.

Use the caller-supplied Qwen Code environment and authentication. Do not redirect its configuration or invent credentials. Discover exact model identifiers from the caller's Qwen Code configuration or `qwen --help`; do not guess. Pass explicit model choices through without capability ranking. Qwen Code effort must remain `default` because the tested command exposes no effort flag; unsupported selections fail before launch.
