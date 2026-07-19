# OpenCode CLI Reference

## Eligibility

OpenCode is eligible as Developer or delegate, in either access mode, regardless of whether its configured model is local, self-hosted, or hosted. The user, plan, or launcher chooses the role, model, and effort. This reference does not rank models.

## Read-only delegate launch

Write schema-v3 policy/request JSON as documented in [delegate-contract.md](delegate-contract.md), then use `delegate_jobs.py launch`. The launcher owns `opencode run`, prompt placement, the model flag, agent choice, auto approval, repository directory, and capture. The tested `opencode run` command has no effort/variant flag, so a non-default effort request fails closed before launch.

Read-only command shape:

```text
opencode run <prompt> [-m <provider/model>] --agent plan --auto --dir <repo>
```

Direct testing established that `--agent plan --auto` is the unattended read-only configuration. The plan agent denies edit tools, but shell execution remains available and is constrained by the read-only prompt. Enforcement is therefore partial. `--auto` prevents a headless approval hang; it does not convert the delegate into an editor.

## Read-write delegate launch

Only valid against a policy whose `required_access` includes `read-write`. The launcher selects `--agent build` instead of `--agent plan`:

```text
opencode run <prompt> [-m <provider/model>] --agent build --auto --dir <repo>
```

`build` is OpenCode's primary agent; `opencode agent list` reports it with an unconditional `"permission": "*", "action": "allow"` rule, i.e. no built-in restriction on tool use. Enforcement of the request's `authorized_surface` is therefore entirely prompt-based — there is no mechanical write boundary for this harness in either access mode. `--auto` remains required to avoid a headless approval hang; it does not add any restriction on what `build` may touch.

## Lifecycle

OpenCode has no dedicated session-log integration in the helper. `activity` uses helper-managed file/process signals. Use `wait`, `extract`, and `cancel` normally. Cold local models can be quiet; silence alone is not a hang while the process is healthy.

Do not resume through raw `--continue` or `--session` commands. Write a new validated request with an `-rN` label.

## Configuration

Discover exact model identifiers from the caller's OpenCode configuration or `opencode models`; do not guess. Pass explicit model choices through without capability ranking. OpenCode effort must remain `default` because the tested CLI exposes no effort flag; unsupported selections fail before launch.
