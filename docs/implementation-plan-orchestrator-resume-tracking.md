# Implementation Plan — Orchestrator: session resume + all-harness tracking parity

## Purpose

Give the orchestrator two capabilities it lacks today, so all five supported harnesses (Claude Code, Codex CLI, GitHub Copilot CLI, OpenCode, Qwen Code) are genuinely first-class:

1. **Session resume (continuation).** Today the orchestrator forbids continuing a delegate's harness session — the five reference files each say "do not resume through a raw command; write a new `-rN` request." That prohibition exists for auditability, not because resume is unsound. This plan adds a *validated* continuation: an `-rN` request that continues a prior delegate's captured harness session, re-checked against policy on every turn. It enables the review→fix workflow (a read-only delegate reviews a diff, then a read-write continuation resolves the findings while the code is still in its context) without re-establishing context from scratch.
2. **All-harness activity/log tracking.** Today rich activity signals (session-transcript discovery, last-assistant timestamps) exist only for Claude and Codex (`delegate_sessions.py`); Copilot/OpenCode/Qwen fall back to file-mtime only. This plan levels the five up to a common signal, capturing each harness's session id and reading real activity where the harness exposes it, with the universal captured-outfile signal as the floor where it does not.

## Relationship to the headless-Developer plan (connected, not coupled)

This plan is a **sibling** of `docs/implementation-plan-headless-developer.md`. They share design *philosophy* (headless launch, session-id capture, per-harness resume syntax, all-harness parity) but by explicit architectural decision they **share no code**: the `project-manager` skill re-specs its own thin launcher rather than importing the orchestrator substrate, exactly as `review.py` today re-specs the orchestrator's command table as "behavioural evidence." The one deliberately-duplicated artifact across the two plans is the per-harness *launch + resume command syntax*; each skill owns its own copy. A reviewer holding both plans should confirm that (a) neither plan introduces a cross-skill import, and (b) the per-harness command/resume syntax is factually consistent between the two even though the code is separate.

## Current-state facts this plan relies on (verify during review)

- `delegate_jobs.py` launches delegates detached (a detached wrapper `Popen` with `start_new_session=True`, which in turn launches a separately-sessioned child `Popen` — two process layers, not classic double-fork daemonisation), tracks them across CLI invocations via a per-run `manifest.json` + `<label>-status.json` + state-dir `index.json`, and exposes `init/profiles/launch/status/activity/wait/extract/cancel/_runner`. There is no resume subcommand.
- Session-id capture and transcript activity are implemented for `claude` and `codex` only (`delegate_sessions.py resolve_session_path`/`session_activity` return `None`/`{}` for the other three). Copilot/OpenCode/Qwen use newest-mtime among outfile/errfile/status_file.
- All five harnesses' CLIs support resume: `claude --resume <id>` / `--session-id <uuid>` (settable), `codex exec resume <id>|--last`, `copilot --resume[=id]` / `--session-id <id>` (settable), `opencode run --session <id>|--continue`, `qwen --resume <id>|--continue`. Only Claude and Copilot allow *setting* the id at launch; the other three must have it captured post-launch.
- The raw-resume prohibition is documented in the five harness reference files: `claude.md:33`, `codex.md:33`, `copilot.md:27`, `opencode.md:33`, `qwen.md:23`. (`SKILL.md:91` forbids bypassing a *rejected* request with a raw command — a related but distinct rule this plan does not change.)

## Implementation Profiles

- Recommended for frontier/senior implementer: run Batch A (Slices 1–2), then Slice 3, then Slice 4.
- Recommended for standard implementer: run slices individually, validating after each.
- Recommended for weaker implementer: run atomic slices one at a time; Slice 3 is elevated risk.

## Slice Batches

- Batch A: Slices 1–2 — session-id capture and activity parity are the read/track foundation; they share one lifecycle-test surface and do not change launch or continuation semantics.

## Slice 1: Capture and persist a harness session id for all five tools

### Intended Change
- Generate a UUID and pass it at launch for the harnesses that accept one (`claude --session-id <uuid>`, `copilot --session-id <uuid>`), composed in `delegate_contract.py`'s command builder.
- For the harnesses that do not accept a settable id (`codex`, `opencode`, `qwen`), capture the id post-launch and **bind it to this launch** — never a bare "most recent" store query, which in a multi-job run could persist an unrelated process's id. `codex` reuses the existing launch-correlated resolver (stdout `session id:` plus a store record matched by prompt/cwd/start-time, as `delegate_sessions.py` already does); `opencode`/`qwen` get an equivalent resolver correlating the store record to this launch's prompt/cwd/start-time. When ownership cannot be established, record `session_id: null` rather than a guessed id.
- Persist `session_id` (and `session_path` where a transcript file exists) into the run `manifest.json` entry for all five tools, and surface it in the `status`/`activity` output.

### Acceptance Criteria
- Inputs: a `delegate_jobs.py launch` for each of the five tools.
- Outputs: the manifest entry for every tool carries a `session_id` field (a real id where the harness exposes one; `null` only where genuinely unavailable); `status`/`activity` report the captured id.
- User-visible behaviour: `status`/`activity` can report the session id for any tool.
- Behaviour that must not change: existing claude/codex capture behaviour; the schema-v3 request/policy contract; launch success for a tool whose id cannot be captured (it must still launch and track).

### Authorized Surface
- Files allowed to change:
  - `skills/orchestrator/scripts/delegate_jobs.py`
  - `skills/orchestrator/scripts/delegate_sessions.py`
  - `skills/orchestrator/scripts/delegate_contract.py`
  - `skills/orchestrator/tests/`
- Functions/classes/components allowed to change: the launch/session-capture path in `delegate_jobs.py` (including the manifest-write and the `delegate_status`/`command_status`/`command_activity` output paths that must report the id); per-harness id/transcript discovery in `delegate_sessions.py`; command composition (`--session-id` addition) in `delegate_contract.py`.
- Tests allowed or expected to change: `skills/orchestrator/tests/test_delegate_sessions.py`, `skills/orchestrator/tests/test_delegate_contract.py`, and new lifecycle tests under `skills/orchestrator/tests/`.

### Explicit Non-Goals
- No resume/continuation behaviour yet (Slice 3).
- No change to the delegate contract's access modes or "never commits" rule.
- No import of orchestrator code into `project-manager`, or vice versa.

### Risk Flags
- Risky surfaces touched: none
- Approval needed before implementation: no

### Validation Plan
- Tests to add/update: per-tool session-id capture (settable for claude/copilot; launch-correlated for codex/opencode/qwen; `null` fallback path). Assert the manifest carries the field and `status`/`activity` report it for all five. Include a negative test: a newer *unrelated* session in the store for the same tool is **not** mis-captured — capture correlates to this launch or records `null`.
- Commands to run: `python3 -m pytest skills/orchestrator/tests/`
- Manual checks: `python3 skills/orchestrator/scripts/delegate_jobs.py profiles`; optionally a live smoke launch per installed tool confirming an id is captured (or a recorded reason it was not).

### Rollback Path
- Revert the slice commit; capture reverts to claude/codex-only. The `session_id` field is additive and tolerated-absent, so no persisted-state migration is required.

## Slice 2: All-harness activity/log tracking parity

### Intended Change
- Extend `delegate_sessions.py` so `session_activity`/`resolve_session_path` produce real activity signals for `copilot`, `opencode`, and `qwen` (transcript/session-store discovery + last-activity timestamp) rather than returning `{}`.
- Where a harness exposes no machine-readable transcript, use the newest mtime of the captured outfile as the activity signal, so `activity` reports a comparable health signal for every tool with none silently unmonitored.
- Make `command_activity` treat all five uniformly.

### Acceptance Criteria
- Inputs: `delegate_jobs.py activity` against a tracked delegate of each tool.
- Outputs: a populated activity payload for every tool (transcript-derived where available, outfile-mtime-derived otherwise), with the source of the signal identifiable.
- User-visible behaviour: no tool reports an empty/absent activity payload while its process is alive.
- Behaviour that must not change: claude/codex transcript-derived richness; `--max-idle` semantics; liveness/cancel identity checks.

### Authorized Surface
- Files allowed to change:
  - `skills/orchestrator/scripts/delegate_sessions.py`
  - `skills/orchestrator/scripts/delegate_jobs.py`
  - `skills/orchestrator/tests/`
- Functions/classes/components allowed to change: `session_activity`, `resolve_session_path`, `extract_session_text` dispatch, and `command_activity`/`helper_activity` in `delegate_jobs.py`.
- Tests allowed or expected to change: `skills/orchestrator/tests/test_delegate_sessions.py` and new activity tests under `skills/orchestrator/tests/`.

### Explicit Non-Goals
- No resume behaviour (Slice 3).
- No change to launch or contract semantics.

### Risk Flags
- Risky surfaces touched: none
- Approval needed before implementation: no

### Validation Plan
- Tests to add/update: activity payload is non-empty for each of the five tools; the outfile-mtime fallback path is exercised for a tool with no transcript; claude/codex richness preserved.
- Commands to run: `python3 -m pytest skills/orchestrator/tests/`
- Manual checks: optional live `activity` against an installed tool of each family.

### Rollback Path
- Revert the slice commit; the three tools return to file-mtime-only tracking. No state migration.

## Slice 3: Validated session resume (continuation) for all five tools

### Intended Change
- Add per-harness resume command composition in `delegate_contract.py` (`claude --resume <id>`, `codex exec resume <id>`, `copilot --resume=<id>`, `opencode run --session <id>`, `qwen --resume <id>`), always using an explicit captured session id.
- Add a continuation launch path in `delegate_jobs.py`: a new `-rN`-labelled schema-v3 request that names the prior delegate and continues its captured session. The continuation request is **validated against policy exactly like a first launch** (tool, model, effort, access) — a continuation may change access mode (read-only review → read-write fix) only if policy authorises it. The continued turn remains bound by every delegate rule: it never commits, never re-delegates, and a read-write continuation still requires `authorized_surface`/`non_goals`.
- **Continuation requires a verified parent-session identity**: the named parent must (a) exist in the same managed run, (b) be terminal, (c) use the same harness/tool, (d) own a captured session id, and (e) carry `-rN` label lineage. If the parent has no captured session id, the continuation **blocks with a clear error** — there is no global "resume last" fallback, which in this multi-job substrate could continue an unrelated session.
- Record the continuation's parent label/session in the manifest so the lineage is auditable.

### Acceptance Criteria
- Inputs: a completed delegate with a captured session id, then a continuation request with an `-rN` label referencing it.
- Outputs: a new tracked delegate that continues the same harness session, with its own status/outfile artifacts and a recorded parent link.
- User-visible behaviour: the review→fix workflow works end-to-end for each tool; a parent with no captured id yields an explicit block, never a wrong-session resume.
- Behaviour that must not change: first-launch validation; the "never commits / never re-delegates" invariants; policy-authorised access enforcement.

### Authorized Surface
- Files allowed to change:
  - `skills/orchestrator/scripts/delegate_jobs.py`
  - `skills/orchestrator/scripts/delegate_contract.py`
  - `skills/orchestrator/scripts/delegate_sessions.py`
  - `skills/orchestrator/tests/`
- Functions/classes/components allowed to change: request validation + launch path (continuation branch, parent-identity check) in `delegate_jobs.py`; resume-command composition in `delegate_contract.py`; any session-id resolution helper needed for resume in `delegate_sessions.py`.
- Tests allowed or expected to change: `skills/orchestrator/tests/test_delegate_contract.py`, `skills/orchestrator/tests/test_delegate_sessions.py`, and new continuation tests under `skills/orchestrator/tests/`.

### Explicit Non-Goals
- No raw/unvalidated `--resume` bypass; continuation always re-validates against policy.
- No global "resume last" fallback.
- No delegate commit/re-delegation authority.
- No `project-manager` integration in this plan.

### Risk Flags
- Risky surfaces touched: delegate lifecycle semantics and the launch/validation contract (a new continuation branch that continues a live harness session and lifts a documented resume prohibition)
- Approval needed before implementation: no
- Independent audit required: yes

### Validation Plan
- Tests to add/update: continuation composes the correct per-harness resume command from a captured id; the parent-identity gate rejects a non-terminal, cross-run, cross-harness, or id-less parent (with a clear error); re-validates against policy (rejects an access mode the policy does not authorise); records parent lineage; a read-write continuation still requires `authorized_surface`/`non_goals`.
- Commands to run: `python3 -m pytest skills/orchestrator/tests/`
- Manual checks: a live read-only review followed by a continuation on at least one installed tool (e.g. codex), confirming the second turn has the first turn's context.

### Rollback Path
- Revert the slice commit; the orchestrator returns to one-shot-only delegates. Slices 1–2 (capture/tracking) remain valid independently.

## Slice 4: Documentation, references, and CHANGELOG for resume + parity

### Intended Change
- Update the five harness reference files to replace the raw-resume prohibition with the validated `-rN` continuation contract, and to state each tool's session-id capture and activity-tracking behaviour.
- Update `SKILL.md` (lifecycle section) and `references/delegate-contract.md` / `references/templates.md` to document the continuation request shape, the parent-identity requirement, and lineage.
- Update `skills/orchestrator/README.md` (its `delegate_sessions.py` description), the top-level `README.md` orchestrator description, and `CHANGELOG.md`.

### Acceptance Criteria
- Inputs: the docs as they stand after Slices 1–3.
- Outputs: no reference file still forbids resume outright; the continuation contract (including the parent-identity requirement and block-on-missing-id behaviour) and all-harness tracking are documented in exactly one authoritative place each.
- User-visible behaviour: a reader can write and launch a valid continuation request from the docs alone.
- Behaviour that must not change: the delegate role model (never commits), tool-equality framing, schema-v3 field discipline.

### Authorized Surface
- Files allowed to change:
  - `skills/orchestrator/SKILL.md`
  - `skills/orchestrator/references/claude.md`
  - `skills/orchestrator/references/codex.md`
  - `skills/orchestrator/references/copilot.md`
  - `skills/orchestrator/references/opencode.md`
  - `skills/orchestrator/references/qwen.md`
  - `skills/orchestrator/references/delegate-contract.md`
  - `skills/orchestrator/references/templates.md`
  - `skills/orchestrator/README.md`
  - `README.md`
  - `CHANGELOG.md`
- Functions/classes/components allowed to change: n/a (documentation).
- Tests allowed or expected to change: none expected.

### Explicit Non-Goals
- No behavioural code change (that lands in Slices 1–3).
- No edit to `docs/VISION.md` (already harness-neutral).

### Risk Flags
- Risky surfaces touched: none
- Approval needed before implementation: no

### Validation Plan
- Tests to add/update: none.
- Commands to run: `rg -n "do not resume|Do not resume|do not continue" skills/orchestrator/references` returns nothing.
- Manual checks: a reader can follow `templates.md` to write a continuation request; `README.md`/`CHANGELOG.md` describe resume + all-harness tracking accurately.

### Rollback Path
- Revert the slice commit; documentation returns to describing one-shot-only delegates.

## Next Chat Prompt

```md
Plan file: docs/implementation-plan-orchestrator-resume-tracking.md
Slices or batch this session: Slice 1 (or Batch A: Slices 1–2)

Read the full plan file first. If a selected slice receipt is incomplete or the repo state is unclear, stop and tell me before coding.

Work on the current feature branch (feature/headless-developer) unless told otherwise.

Use orchestrator as the controlling skill. Act as the Developer: keep implementation, validation, Git operations, and commits local.

For each selected slice, in plan order: restate the frozen contract; apply scoped-implementation; apply drift-audit and report the gate result; on a passing gate apply code-review; surface findings, fix, re-gate; then ask before committing.

Slice 3 is marked "Independent audit required: yes": commission independent read-only drift-audit and code-review delegates for it. If no independent Reviewer can be launched for Slice 3, STOP and report rather than self-audit it. (Slices 1, 2, and 4 are standard: Developer self-audit is acceptable when no Reviewer is available, recorded as such.)

Confirm before starting: plan file read, selected slice(s), branch, and the first slice.
```
