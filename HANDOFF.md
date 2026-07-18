# HANDOFF

## Objective
- Complete the approved Mode B Lite greenfield replacement of the Project Manager system, per the binding six-report spec in `docs/mode-b-lite/` (authority order: proposed-vision → target-design → replacement-ledger → implementation-blueprint; stage order = blueprint §3). Do not re-litigate the design.

## Task List
- [x] Deletion first commit (`f9d36a3`): old `skills/project-manager/`, `pm-slice-contract.md`, PM-facing orchestrator machinery removed; orchestrator standalone suite green (26 tests).
- [x] Stage 1 (`20e6ecc`): `pm_lib/{state,plan,git_ops,cli}.py` + `pm.py` — lite-1 HMAC-authenticated single-copy state, plan parser + mechanical `plan_risk`, segment-aware surface matching.
- [x] Stage 2 (`c767127`): `sessions.py`, `profiles.py`, `floor.py` — eight-fact floor, hard-stop markers, four harness profiles.
- [x] Stage 3 (`b41acaa`): `slice_ops.py`, `prompts.py`, `references/developer-prompt.md`, CLI wiring — full lifecycle, evidence-mode finalize.
- [x] Stage 4 (`db0f0f2`): `review.py`, `references/reviewer-prompt.md`, finalize `--accept/--steer/--stop`, review freshness, controller-owned originals + `.pm/` mirrors, run report. Suite: 252 tests green, zero skips.
- [ ] Stage 5 — Documentation & operator trial. Draft docs ALREADY IN WORKTREE, untracked: `skills/project-manager/SKILL.md` (61 lines; cap ≤~130), `README.md` (111), `references/run-state.md` (65). AC: docs accurate vs shipped CLI; the README "Verify your setup" fake-harness trial runs green from a clean checkout; a fresh reader can run a toy plan from the docs alone (this new session IS that fresh-reader test).
- [ ] Stage 6 — Cutover: root README Mode B sections, CONTRIBUTING doc map, `implementation-plan`/`handoff`/`report` SKILL.md texts, `.gitignore` (`.ai-pm` → `.pm`), `ci.yml` paths, orchestrator doc simplification sweep, replace `docs/VISION.md` with `docs/mode-b-lite/proposed-vision.md` (same change-set, never earlier), run blueprint §6 no-baggage checks (terminology grep list = ledger §8; add grep to CI). **Ask the owner before Stage 6.**
- [ ] Stage 7 — Validation: Run C (scripted adversarial fake-harness scenarios, blueprint §7) is mechanisable now; Runs A/B need the owner's local model pairings and cost real usage — **report to owner before running**. Update blueprint §9 metrics with measured values; CHANGELOG adoption entry.

## Current Status
- Branch `feature/mode-b-lite-impl`; committed through Stage 4; working tree contains ONLY the three untracked Stage 5 doc drafts.
- `python3 -m unittest discover -s skills/project-manager/tests -p 'test_*.py'` → 252 tests OK (tmux present). Orchestrator suite separately green.

## Decisions Made
- Owner authorized: commit per stage once its ACs pass, no per-commit approval; owner gates Stage 6 and Stage 7 live runs.
- Delegation policy (owner instruction): all non-trivial coding via Sonnet subagents from a frozen written brief, tests written first; the lead session reviews every module, independently verifies stage ACs end-to-end, and owns the commit.
- IntegrityError is terminal: never rewrite/re-sign state after a MAC failure (re-signing would launder tampered bytes); tampered `run.json` survives as evidence and every mutating command keeps failing closed.
- `--risk elevated` ratchet flag on `start-slice`/`finalize` (raise-only; `plan_risk` immutable) and `review --reviewer-command` test hook are deliberate, recorded implementations of designed behaviour — not drift.
- Elevated acceptance mechanically requires BOTH drift-audit and code-review reviews fresh for the exact final HEAD (sha256-verified artifacts); `finalize --accept` needs ≥40-char reasoning and a passing floor.
- `PM_NOTES_PATH` points at the `.pm/` mirror; controller originals live under `<git-dir>/pm/<run-id>/`; report regenerates from controller data only.

## Failed or Rejected Approaches
- Stage 4 subagent's "heal" of tampered state (re-sign + needs-human) — rejected and replaced (see Decisions); the tamper test now pins the terminal behaviour.
- Stage 4 subagent died at a usage limit before its final report; lead completed verification directly — nothing pending from it.
- Fake-harness test scripts must drain stdin (`cat -`), not bare `sleep`: the pasted multi-KB prompt can saturate the pty input queue and silently drop a later steer line (documented in `test_slice_ops.py`).

## Active Blockers
- None technical. Stage 6 and Stage 7 (Runs A/B) await explicit owner go-ahead.

## Files That Matter
- `skills/project-manager/scripts/pm_lib/*.py` — the complete toolkit (11 modules); `tests/` — 252 tests, fake-harness pattern.
- `skills/project-manager/{SKILL.md,README.md,references/run-state.md}` — UNTRACKED Stage 5 drafts to review/validate/commit.
- `references/{developer-prompt.md,reviewer-prompt.md}` — committed prompt templates (single ```md fence each; str.format contract).
- `docs/mode-b-lite/implementation-blueprint.md` — §3 stage ACs, §6 no-baggage checks, §7 validation plan, §8 stop rule.
- `docs/mode-b-lite/replacement-ledger.md` — §8 terminology grep list, §9 sanctioned carry-overs.
- `.github/workflows/ci.yml` — still points at deleted PM test paths; fix in Stage 6.

## Validation
- Done: full suite per stage; independent end-to-end CLI verification of every stage AC (fake harness in scratch repos): 8-fact floor evidence, branch-switch fails facts 2+6, credential-pane fails only fact 8, token gating + INTEGRITY terminality, attempt rotation/budget, scavenge with state deleted, standard + elevated acceptance, staleness invalidation, report with `.pm/` deleted, transitive bundle embeds `review-matrix.md`.
- Still needed: Stage 5 doc-accuracy pass + trial run from the drafts; Stage 6 no-baggage greps; Stage 7 runs.

## Authorization Gate
- Not a scoped-implementation slice; governed by blueprint §8: any deviation touching roles/gates/floor/state/commands/artifacts/risk/authority requires amending `docs/mode-b-lite/` first in a dedicated commit. None has been needed so far.

## Next Action
- Start Stage 5: read the three untracked draft docs against the shipped CLI (`python3 skills/project-manager/scripts/pm.py --help` and each subcommand), fix any drift (e.g. verify every flag named in README exists), then execute the README "Verify your setup" trial verbatim in a scratch directory as the fresh-reader test, then commit Stage 5 as one commit. Delegate mechanical doc-vs-CLI checking to a Sonnet subagent if desired; the trial itself is the lead's to run.
