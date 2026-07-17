# Changelog

Notable changes to this repository. Format follows [Keep a Changelog](https://keepachangelog.com/); versions follow [SemVer](https://semver.org/) once tagged. Releases are tagged from `main`; v1.0.0 will mark the first stable contract for the skills, the Project Manager CLI, and the plan format.

## [Unreleased]

### Added

- Mechanical repair-round ledger-retention gate (`ledger-retention`): a passing repair result that silently drops a previously archived residual finding or continuation note now fails the gate, except for the round immediately following a `context-budget` repair, which is exempt because that repair requires condensing and rewording ledger items.
- Slice-entry evidence fields previously left unchecked by run-state validation (`summary`, `changed_files`, `validation`, `drift_audit`/`code_review`, `commit`, `blockers`, `next_action`, `residual_findings`, timestamps) are now shape-validated on load, with persist-time normalization of malformed Developer-reported values to their documented defaults so a garbage result can never wedge a terminal state write.

### Changed

- **Breaking:** Project Manager run state and Developer results now use schema version 5. Every slice entry persists and validates `prior_slice_context` (the protected prior-slice-context digest carried forward from the attempt that produced it) so a later `reconcile` can re-verify it out-of-process, and `current_slice` and every terminal entry require an explicit `repair` state object; runs on an earlier schema must be reinitialized. This and the following two entries close gaps identified in `docs/report-code-review-and-simplification-20260716.md`.
- `reviewer-policy.json` now binds `before_head`, `session_generation`, and `repair_round`, and is rewritten — together with the persisted `current_slice.reviewer_policy` snapshot — at the start of every repair round, so a Reviewer `PASS` obtained before a tree-changing repair can no longer satisfy an opt-in independent-audit gate for work the Reviewer never saw.
- `reconcile` now re-runs the prior-slice-context integrity check and the next-slice context-budget projection before accepting a stopped slice — both refusals are terminal and never steered, matching the runner's own gate — and cancels any leftover tracked reviewers. Slice finalization builds the persisted slice entry once from the same `reviewer-runs-summary.json` snapshot the gate verified, then cancels reviewers afterwards, so an adversely-completing reviewer run can no longer diverge the durable record from the evidence the gate actually checked.
- The failure-signature taxonomy in `gates.py` (`REPAIRABLE_SIGNATURES`/`TERMINAL_SIGNATURES`) is now genuinely complete and authoritative: every gate failure, including `transient-service-unavailable`, `idle-no-progress`, and `prior-context-integrity`, is constructed through it instead of bypassing it. The duplicated continuation-note and residual-finding ledger validators in `gates.py` and `state.py` are unified into one shared validator.
- The external-side-effect prompt regex — enforced at two layers, the send-time hard-prompt guard and operational-hint extraction — is now defined once in `constants.py` and imported by both, so a pattern fix can no longer leave one layer stale.
- **Breaking:** Project Manager state/results were bumped to schema version 4 (superseded by schema version 5 above within this unreleased cycle). Passing slice results require a structured `continuation_notes` ledger for decisions, implementation and interface lessons, failed approaches, validation/tooling knowledge, risks, and later-slice guidance; older runs must be reinitialized.
- Mode B now generates a hash-addressed, provenance-labelled `prior-slice-context.md` for every slice from the authoritative accepted outcomes of earlier slices. Fresh Developers must read this bounded history alongside the plan and current frozen contract, while controller state, raw transcripts, superseded outcomes, and authorization remain isolated.
- Slice completion now follows the latest authoritative outcome consistently across selection, reports, and cross-slice context; a superseded earlier pass no longer keeps a slice marked complete after a later terminal outcome.
- **Breaking:** renamed the `master-controller` skill and MC identity to `project-manager` and PM. Active CLI/package paths, runtime state, environment variables, session prefixes, cross-skill contracts, tests, CI, and documentation now use PM terminology without compatibility aliases; existing `.ai-mc/` runs remain historical evidence and new runs initialize under `.ai-pm/`.
- **Breaking:** renamed the `ai-orchestrator` skill to `orchestrator`, renamed the executing agent role to Developer, and replaced the Senior/Junior worker roles with one read-only Reviewer role. All supported harnesses are equally eligible for either role; harness-specific read-only enforcement differences are reported as facts rather than used as eligibility policy.
- **Breaking:** the Reviewer contract uses schema version 2. The CLI uses `--reviewer-*`, runtime state lives under `.orchestrator/`, and Developer/Reviewer fields and artifacts replace their former role-shaped names without compatibility aliases.
- Audit provenance now records Reviewer execution or explicit Developer self-audit in slice summaries, run reports, and summaries. Default slices may self-audit when no Reviewer is configured or available; independent-audit slices still require separate validated Reviewer runs.
- `pm_lib`'s re-export facade (`__init__.py`) is retired in favor of direct submodule imports; `pm.py` now imports only the CLI entry point.
- `runtime.py` is split into `hints.py` (operational-hint extraction), `prompts.py` (prompt/repair-template rendering), and `context.py` (prior-slice-context generation, budget projection, and integrity), keeping `runtime.py` as the residual (environment/paths, reviewer policy/credentials, transcript and reviewer-run capture/cancel). A pure verbatim move with no behavior change.
- The untested, ungated `ai-reminder` utility is archived out of the orchestrator skill (recoverable from git history); it duplicated domain knowledge maintained and tested elsewhere.

### Fixed

- `reviewer_jobs.py wait` now exits nonzero for a reviewer wrapper that died before writing its status file, instead of misleadingly reporting success. PM's evidence gate already rejected such runs, so this fixes only the helper's exit code.

## [0.5.0] — 2026-07-13

### Added

- Mode B residual-finding propagation: every passing orchestrator result carries a structured `residual_findings` ledger, MC writes a per-slice `slice-summary.md`, and every run-state update refreshes an aggregate `run-report.md` so non-blocking post-plan considerations survive fresh sessions and repair rounds.

### Changed

- **Breaking:** Master Controller durable state and orchestrator results now use schema version 2. MC supports only the current complete state shape; runs missing the frozen plan digest, supervision/event state, repair state, worker posture, or recorded Git boundary must be reinitialized instead of being inferred or migrated.
- MC opt-in independent audits now require separate validated worker contracts for `drift-audit` and `code-review`; prompts require the drift verdict before code review launches and preserve the original delegation posture during repair.
- MC slice prompts embed a compact 615-word delegation contract instead of the full transitive `ai-orchestrator` skill and every harness reference.
- Mode A handoff/final-report guidance and Mode B reporting now preserve the same residual post-plan considerations without using a repo-root `HANDOFF.md` as Mode B continuation state.

### Fixed

- MC's prompt now matches its exact-`PASS` code-review gate and distinguishes reportable pre-existing or unrelated observations from material slice-caused defects that must still stop the run.

## [0.2.0] — 2026-07-13

### Added

- `docs/VISION.md`: the repository's timeless vision — problem, commitments, autonomy ladder, roles, personas, design principles, non-goals.
- `check-plan`: whole-plan pre-run sanity check in Master Controller (also runs automatically at `init`, failing closed on errors). Validates every slice's required sections, authorized surface, and approval flag, and lints for dependency/license-shaped authorized files, whole-repo surfaces, and Mode A-only batch groupings.
- "Privacy and Data Flows" in the master-controller README: per-seat data visibility, fully-local configurations, and an artifact sensitivity map.
- `skills/master-controller/AGENTS.md`: maintainer guide with file roles, working rules, test matrix, and change checklists.
- CI (GitHub Actions): compile checks plus both unit suites, including tmux-backed runtime tests with fake harnesses.
- `CONTRIBUTING.md`: source-of-truth map, test matrix, and change conventions.
- `archive/docs/pre-schema-v2-20260713/repo-review-vision-rubric-20260712.md`: repository-wide code-review and simplification assessment measured against the vision's eight design principles (archived after the schema-v2 reset).

### Changed

- Top-level README reframed around the autonomy ladder (Rung 0 → Mode A → Mode B) with a quickstart, decision table, glossary, and validation note; identity is now explicitly "autonomy system first".
- Mode taxonomy simplified from four labels (A / B / C1 / C2) to two modes: the former Mode B (autonomous single session) is now the documented autonomous alternate usage of Mode A — same session, same launcher family, standing commit authorization — and supervised autonomy under Master Controller is Mode B, model-supervised by default with a fail-closed unattended batch fallback (the former C1/C2 fork). No CLI behavior changed.
- Launcher templates single-sourced: both Mode A launchers (checkpointed and autonomous) live in `implementation-plan`'s SKILL.md, the Mode B launcher lives in `master-controller`'s SKILL.md, and the handoff resume prompt is derived from the checkpointed Mode A launcher instead of restating it.
- Master Controller SKILL.md: headline verification claim aligned with the documented trust boundary; new "Roles and Topology" section naming all four seats (supervising model, MC deterministic tools, slice orchestrator, worker) and what each may decide.
- `implementation-plan`: new "Execution Modes" section stating which plan features bind in which mode; Mode B (Master Controller) added to the launcher choices as a pointer; output rule keeping dependency/license files out of unattended authorized surfaces.
- `ai-orchestrator` SKILL.md: MC-specific requirements consolidated into one "Under Master Controller" section; skill map trimmed to skills that exist in this repository.
- `ai-orchestrator` worker management split by responsibility: vendor-specific session discovery, activity interpretation, and transcript extraction now live in `worker_sessions.py`, while `worker_jobs.py` retains contract launch, tracked-process lifecycle, and the CLI.
- `stop-with-evidence` now fails closed when the frozen plan changed mid-run; the plan-independent `stop` command remains available for cancellation.
- `code-simplifier` rewritten in the repository's contract style: ecosystem-neutral (standards discovered from the target project), no model pin.
- `master-controller` test suite split from one 4,456-line monolith into seven themed modules plus a shared fixtures module (`mc_test_helpers.py`); test count and coverage unchanged.

### Fixed

- Flaky runtime-test fixture: the hard-prompt-at-repair fake harness now exposes a Codex-ready marker after terminal setup and waits for MC's initial prompt injection before showing its trust prompt, removing a startup race that could time the test out under system load.
- `check-plan` now rejects malformed slice-like headings instead of silently omitting their work, and rejects authorized entries that cannot match repository-relative git paths.
- `check-plan` closes three more silent-mismatch shapes: authorized entries with unwrapped whitespace (usually a trailing annotation like `README.md (new file)`) are rejected — backtick-wrap the path to annotate it; slice-like headings inside fenced code blocks, and unclosed fences, are rejected as ambiguous; and a plain entry that names an existing directory draws a warning when repo context is available (automatic at `init`, and via `check-plan --repo`, default the current directory). The `Slice Batches` lint now fires at any heading level.
- CI now declares a read-only token boundary and does not persist checkout credentials; MC's Python 3.13 minimum is documented consistently with the version CI validates.
- Model-supervised startup failures now retain the underlying exception in run state instead of recording only a generic launch failure.
- Master Controller's known unattended launch commands are derived from harness profiles, authorized-surface matcher parity is regression-tested across MC and ai-orchestrator, and literal tmux sends terminate option parsing safely.

## [0.1.0] — 2026-07-10

Initial public import of ten modular AI engineering skills from the private bootstrap repository, including the master-controller supervision runtime, the ai-orchestrator semantic worker launcher, and the plan/implementation/audit/review/commit skill chain.
