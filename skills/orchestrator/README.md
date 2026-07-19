# Orchestrator

A vendor-neutral, harness-neutral skill for delegating bounded work to Claude Code, Codex CLI, GitHub Copilot CLI, OpenCode, or Qwen Code while the current Developer retains implementation and final responsibility. Any supported harness can run this skill; any supported harness can be the delegate it launches.

## Operating model

The orchestrator is the workflow, not a person or model tier.

- **Developer**: the session running this skill. Owns planning, coding, testing, verification, gates, commits, and final delivery — including for anything a delegate produced.
- **Delegate (read-only)**: gathers evidence and performs read-only investigation, drift audit, and code review. Never edits, mutates the repository, commits, or re-delegates.
- **Delegate (read-write)**: a bounded implementer. May create, edit, and run commands inside an explicit `authorized_surface`, never past its `non_goals`. Still never performs Git/GitHub mutations, commits, or re-delegates — the Developer reviews its diff and commits it.

There are no senior/junior delegate variants and no harness ranking. Every supported tool is eligible for either role, in either access mode. Harness profiles describe command mechanics and the factual strength of enforcement for each access mode; they do not decide suitability.

Developer self-audit fallback is allowed on default slices when no read-only delegate is configured or available; the final report must identify any self-performed audit and its fallback context. A plan that asks for independent review (`Independent audit required: yes`) deserves separate read-only delegate launches for `drift-audit` and `code-review`; if a delegate cannot be launched for such a slice, stop and report rather than self-audit.

## Package layout

- `SKILL.md` — workflow and role contract
- `references/delegate-contract.md` — schema-v3 policy/request contract
- `references/templates.md` — semantic request examples for both access modes
- `references/{claude,codex,copilot,opencode,qwen}.md` — harness mechanics and enforcement notes for both access modes
- `scripts/delegate_contract.py` — validation, prompt rendering, and command composition
- `scripts/delegate_jobs.py` — tracked delegate lifecycle
- `scripts/delegate_sessions.py` — session discovery and transcript extraction
- `tests/` — contract, launcher, lifecycle, and transcript tests

## Quick verification

```bash
python3 -m py_compile scripts/delegate_contract.py scripts/delegate_sessions.py scripts/delegate_jobs.py
python3 -m unittest discover -s tests
```

Delegate artifacts default to `.orchestrator/runs/`; set `ORCHESTRATOR_ARTIFACT_ROOT` to override. The retired `.ai-orchestrator/` path and schema-v1/v2 contracts are unsupported.
