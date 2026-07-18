# HANDOFF

## Objective
- Complete the approved Mode B Lite greenfield replacement of the Project Manager system, per the binding six-report spec in `docs/mode-b-lite/` (authority order: proposed-vision → target-design → replacement-ledger → implementation-blueprint). Do not re-litigate the design. Stages 1–6 are done; Stage 7 (live validation & reassessment) remains.

## Task List
- [x] Deletion, Stages 1–4 (`f9d36a3`, `20e6ecc`, `c767127`, `b41acaa`, `db0f0f2`): full toolkit (`pm_lib/`, 11 modules), 252 tests green, every stage AC verified end-to-end.
- [x] Stage 5 (`61074d9`): docs validated flag-by-flag against the shipped CLI; README "Verify your setup" trial run verbatim by a fresh session (floor 8/8, acceptance, report, scavenge).
- [x] Stage 6 (this change-set): root README Mode B sections rewritten per Lite; CONTRIBUTING source-of-truth map updated; `implementation-plan`/`handoff`/`report` SKILL.md texts re-bound (`Independent audit required: yes` ⇒ elevated risk); orchestrator docs rewritten standalone-only; `.gitignore` state-dir entry now `.pm/`; `docs/VISION.md` replaced with the adopted vision; blueprint §6 no-baggage greps pass and run in CI (`ci.yml`, two steps with historical-file + orchestrator carve-outs).
- [ ] Stage 7 — Run C (adversarial spot-checks, blueprint §7): scripted fake-harness scenarios replaying known failure shapes — false success report, unauthorized file change, `.pm/` vandalism (must not corrupt PM state or decisions; damaged Developer evidence fails the slice closed via floor fact 4), wrong-slice result, approval-gate bypass. Bar: every one caught or rendered harmless. Mechanisable without owner input.
- [ ] Stage 7 — Run A (killer case, **owner gates**): local pairing qwen3.6-27b Developer / qwen3.6-35b review seat on the `pm-test` fixture's hard 5-slice plan. Bar: ≥ 4/5 slices sound where the four documented baseline runs (Tests 14/16/17/18) got 0/5.
- [ ] Stage 7 — Run B (strong pairing, **owner gates**): Test 6/12-class pairing. Bar: 5/5 parity with fewer PM interventions and materially fewer model interactions (count from `events.jsonl` vs baseline operational events).
- [ ] Stage 7 — bookkeeping: record per run slices completed, wall-clock, interventions, human touches, artifact volume, assessment usefulness; update blueprint §9 metrics as *measured*; write the CHANGELOG adoption entry. If Run A misses the bar, apply blueprint §8: diagnose implementation vs design vs vision — do not patch forward.
- [ ] Blueprint §6.6 anti-resurrection review — a one-time **human** check (no enum failure classifiers, no second state copy, no per-round artifact families, no verdict-string parsing); flagged to the owner, not an agent task.

## Current Status
- Branch `feature/mode-b-lite-impl`; committed through Stage 6. Both test suites green (PM 252, orchestrator 26); no-baggage greps clean and enforced in CI.
- Stage 6 work was independently reviewed pre-commit (see Developer / Reviewer State).

## Decisions Made
- Owner authorized per-stage commits once ACs pass; owner gates Stage 7 Runs A/B (they cost real model usage on the owner's local pairings).
- Stage 7 validation runs use the existing local `pm-test/` fixture (gitignored, own repo) and `pm-test/docs/implementation-plan-hard-pi-convergence.md`; baseline runs execute from a `main` checkout, Lite runs from this branch (blueprint §7).
- Delegation policy: non-trivial coding via Sonnet subagents from frozen written briefs, tests first; the lead reviews, verifies ACs end-to-end, and owns commits.
- IntegrityError is terminal: never rewrite/re-sign state after a MAC failure; tampered `run.json` survives as evidence.
- Elevated acceptance requires BOTH drift-audit and code-review fresh at the exact final HEAD; `finalize --accept` needs ≥40-char reasoning and a passing floor.

## Failed or Rejected Approaches
- Fake-harness scripts must drain stdin (`cat -`), not bare `sleep` — the pasted multi-KB prompt can saturate the pty queue and drop a later steer line (documented in `test_slice_ops.py`). Directly relevant to scripting Run C.
- A subagent's "heal" of tampered state (re-sign + continue) was rejected; the tamper test pins terminal behaviour.

## Active Blockers
- Runs A/B await explicit owner go-ahead and model pairing confirmation. Run C needs no input.

## Files That Matter
- `skills/project-manager/scripts/pm_lib/*.py` + `tests/` — the shipped toolkit and 252-test suite (fake-harness pattern to reuse for Run C).
- `pm-test/` — local validation fixture (own git repo; not tracked here); `docs/implementation-plan-hard-pi-convergence.md` is the Stage 7 plan; `docs/pm-lessons-learnt.md` holds the baseline test record (Tests 14/16/17/18 = the 0/5 baselines).
- `docs/mode-b-lite/implementation-blueprint.md` — §7 validation plan and bars, §8 stop rule, §9 metrics table to update.
- `.github/workflows/ci.yml` — the two no-baggage grep steps; keep them green in any follow-up.

## Developer / Reviewer State
- Orchestrator run dir: `.orchestrator/runs/` (see latest `reviewers-*` entry). Stage 5+6 change-set reviewed pre-commit by codex `gpt-5.6-sol` (high effort, read-only sandbox): drift-audit against the ledger/blueprint dispositions, then code-review. Findings and dispositions are recorded in the Stage 6 commit message.
- Audit provenance: both reviews Reviewer-performed (codex); the lead session verified and dispositioned every finding.

## Validation
- Done: per-stage suites; Stage 5 fresh-reader trial; Stage 6 §6 checks 1–5 (terminology grep, path grep, `pm_lib` import graph stdlib-only, README/CONTRIBUTING link reachability, fixture sweep) all pass locally and the greps run in CI.
- Still needed: Stage 7 Runs A/B/C and the §6.6 human anti-resurrection pass.

## Authorization Gate
- Governed by blueprint §8: any deviation touching roles/gates/floor/state/commands/artifacts/risk/authority requires amending `docs/mode-b-lite/` first in a dedicated commit. None has been needed through Stage 6.

## Next Action
- Script and run Stage 7 Run C: build the five adversarial fake-harness scenarios from blueprint §7 against a scratch clone of `pm-test` (reuse the `--harness-command` pattern from `skills/project-manager/tests/`), record each outcome (caught / rendered harmless) with evidence paths, then report to the owner and request the Run A/B go-ahead and pairing confirmation before any real-model run.
