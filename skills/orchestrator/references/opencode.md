# OpenCode CLI Reference

## Eligibility

OpenCode is eligible as Developer or Reviewer regardless of whether its configured model is local, self-hosted, or hosted. The user, plan, or launcher chooses the role, model, and effort. This reference does not rank models.

## Reviewer launch

Write schema-v2 policy/request JSON as documented in [reviewer-contract.md](reviewer-contract.md), then use `reviewer_jobs.py launch`. The launcher owns `opencode run`, prompt placement, the model flag, plan agent, auto approval, repository directory, and capture. The tested `opencode run` command has no effort/variant flag, so a non-default effort request fails closed before launch.

Reviewer command shape:

```text
opencode run <prompt> [-m <provider/model>] --agent plan --auto --dir <repo>
```

Direct testing established that `--agent plan --auto` is the unattended Reviewer configuration. The plan agent denies edit tools, but shell execution remains available and is constrained by the read-only prompt. Enforcement is therefore partial. `--auto` prevents a headless approval hang; it does not convert the Reviewer into an editor.

The Reviewer must not use shell commands that alter files or repository state. The Developer and repository mutation gates are the backstop.

## Lifecycle

OpenCode has no dedicated session-log integration in the helper. `activity` uses helper-managed file/process signals. Use `wait`, `extract`, and `cancel` normally. Cold local models can be quiet; silence alone is not a hang while the process is healthy.

Do not resume through raw `--continue` or `--session` commands. Write a new validated request with an `-rN` label.

## Configuration

Discover exact model identifiers from the caller's OpenCode configuration or `opencode models`; do not guess. Pass explicit model choices through without capability ranking. OpenCode effort must remain `default` because the tested CLI exposes no effort flag; unsupported selections fail before launch.
