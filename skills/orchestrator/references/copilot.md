# GitHub Copilot CLI Reference

## Eligibility

Copilot is eligible as Developer or Reviewer on the same terms as every supported harness. The user, plan, or launcher chooses the role, model, and effort. There is no junior/senior default.

## Reviewer launch

Write schema-v2 policy/request JSON as documented in [reviewer-contract.md](reviewer-contract.md), then use `reviewer_jobs.py launch`. The launcher owns prompt/model/effort, autopilot, capture, and repository directory flags.

Reviewer command shape:

```text
copilot [--model <model>] [--effort <effort>] -p <prompt> --allow-all-tools --autopilot --silent --add-dir <repo>
```

Copilot currently has no tested mechanical read-only launch flag. Reviewer isolation is therefore prompt-enforced. The command's tool availability must not be mistaken for authorization: the embedded Reviewer contract forbids edits, mutation-prone commands, Git/GitHub mutations, commits, and re-delegation. The Developer and repository mutation gates are the backstop.

This weaker mechanical boundary is reported by `reviewer_jobs.py profiles`; it does not make Copilot ineligible.

## Lifecycle

Copilot has no session-log integration in the helper. `activity` uses helper-managed file/process signals. Use `wait`, `extract`, and `cancel` normally. Do not resume through a raw command; write a new validated request with an `-rN` label.

## Authentication and configuration

Use the caller's signed-in session and configuration. Do not add GitHub toolsets or request Git/GitHub operations for a Reviewer. Explicit model/effort values are passed through without capability ranking; report unsupported selections as launch failures.
