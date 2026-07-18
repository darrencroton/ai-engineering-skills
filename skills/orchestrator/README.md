# Orchestrator

A vendor-neutral Codex skill for delegating bounded read-only review work to Claude Code, Codex CLI, GitHub Copilot CLI, OpenCode, or Qwen Code while the current Developer retains implementation and final responsibility.

## Operating model

The orchestrator is the workflow, not a person or model tier.

- **Developer**: manages the session and owns planning, coding, testing, verification, gates, commits, and final delivery.
- **Reviewer**: gathers evidence and performs read-only investigation, drift audit, and code review.

There are no senior/junior Reviewer variants and no harness ranking. Every supported tool is eligible for either role. Harness profiles describe command mechanics and the factual strength of read-only enforcement; they do not decide suitability.

Developer self-audit fallback is allowed on default slices when no Reviewer is configured or available; the final report must identify any self-performed audit and its fallback context. A plan that asks for independent review (`Independent audit required: yes`) deserves separate Reviewer launches for `drift-audit` and `code-review`; if a Reviewer cannot be launched for such a slice, stop and report rather than self-audit.

## Package layout

- `SKILL.md` — workflow and role contract
- `references/reviewer-contract.md` — schema-v2 policy/request contract
- `references/templates.md` — semantic request examples
- `references/{claude,codex,copilot,opencode,qwen}.md` — harness mechanics and enforcement notes
- `scripts/reviewer_contract.py` — validation, prompt rendering, and command composition
- `scripts/reviewer_jobs.py` — tracked Reviewer lifecycle
- `scripts/reviewer_sessions.py` — session discovery and transcript extraction
- `tests/` — contract, launcher, lifecycle, and transcript tests

## Quick verification

```bash
python3 -m py_compile scripts/reviewer_contract.py scripts/reviewer_sessions.py scripts/reviewer_jobs.py
python3 -m unittest discover -s tests
```

Reviewer artifacts default to `.orchestrator/runs/`; set `ORCHESTRATOR_ARTIFACT_ROOT` to override. The retired `.ai-orchestrator/` path and schema-v1 Worker contracts are unsupported.
