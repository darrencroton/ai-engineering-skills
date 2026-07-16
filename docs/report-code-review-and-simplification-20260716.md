# Code Review and Simplification Report — 2026-07-16

**Revision 2 (same day):** updated after an independent read-only review by a Codex reviewer (`gpt-5.6-sol`, high effort) launched through the `orchestrator` validated contract. Part 4 documents that review, my verification of its claims, and the resulting changes: one new P1 (finding 15), five further new findings (16–21), one original finding withdrawn (12), one reclassified (5 → folded into 17), and several factual corrections marked inline. The verdict changed.

**Scope:** (1) review of the unreviewed commit range `bad9d4e..0b41986` (three commits); (2) holistic review and simplification analysis of the entire repository (excluding `archive/`) against the purpose, personas, and design principles in `docs/VISION.md`.

**Method:** every Python module in `skills/project-manager/scripts/` and `skills/orchestrator/scripts/` was read in full; every `SKILL.md` and reference document was read; the three commits were reviewed diff-by-diff; both test suites were executed; the draft report was then independently reviewed by a second model (Part 4) and every accepted external claim was re-verified against the code by the author. This report is analysis only — no code was changed.

**Test evidence (run on this machine, Python 3.13, tmux present):**

- Project Manager suite: `python3 -m unittest discover -s skills/project-manager/tests` → **274 tests, OK** (126.9 s)
- Orchestrator suite: `python3 -m unittest discover -s skills/orchestrator/tests` → **26 tests, OK** (2.3 s)

---

## Verdict

**FAIL — one P1 must be fixed; everything else is PASS WITH RISKS territory.** *(Revised after the independent review in Part 4; the original assessment said "no P0 or P1" — that was wrong.)* The P1 is finding 15: on a slice marked `Independent audit required: yes`, Reviewer PASS evidence is not bound to the attempt, repair round, or reviewed tree state, so the mechanical independent-audit gate can be satisfied by audits of code that later changed — reachable in fully unattended operation through ordinary tree-changing repairs. The fix is small (bind the reviewer policy digest to `before_head`/attempt and refresh it per repair round).

Beyond that single blocker, the picture from the original review stands: the commit range is well built, the codebase is unusually disciplined for its size (~9,000 lines of runtime Python, ~6,600 lines of tests, ~5,500 lines of contract documentation), and the repository is genuinely fit for the three personas in the vision. The remaining risks are P2/P3: the `reconcile` acceptance path bypasses two of the newer gates (finding 16), a verification/finalization race on reviewer verdicts (17), documentation drift in one source-of-truth contract, a handful of one-source-of-truth violations in code, one large utility living entirely outside the quality gates, and several duplication hotspots.

---

## Part 1 — Commit-Range Review (`bad9d4e..0b41986`)

### `dc0aa25` — Rename Master Controller to Project Manager

Mechanical identity migration across code, tests, CI, docs, and cross-skill contracts. **Clean.** A repo-wide scan found no leftover `master controller` / `mc` / `.ai-mc` references outside the changelog and one deliberate historical note in `pm_test_helpers.py:3` (which correctly points at the archive). The runtime namespace migration (`.ai-mc` → `.ai-pm`, schema bump) is recorded in `CHANGELOG.md` as breaking, and the no-migration policy in `run-state-schema.md` is honoured (old runs must re-`init`). No findings.

### `9774f49` — Carry slice context across PM sessions (schema v4)

The substantive commit: every Mode B Developer now receives a digest-protected, provenance-labelled `prior-slice-context.md` rendered from authoritative accepted outcomes, plus a structured `continuation_notes` ledger in the developer result, with a byte budget enforced at acceptance time and re-enforced fail-closed at launch time.

**Design assessment — sound.** The security-relevant choices are correct:

- Context integrity is checked *before* the gate at finalize (`prior_slice_context_integrity_failure`), and a mismatch is terminal `needs-human`, never steered — consistent with the "integrity breaches are never repaired" invariant.
- The context artifact carries explicit "historical data, not instructions" framing and per-field provenance labels (`pm-verified` / `developer-reported` / `operator-attested`), which is exactly the honest-threat-model posture the vision requires.
- The acceptance-time budget projection (`projected_prior_slice_context_budget_failure`) renders the *actual* next slice's cumulative context; the launch-time check in `write_prior_slice_context` remains a fail-closed backstop if the projection is ever wrong. The layering is correct **on the runner path — but not on the `reconcile` path, which bypasses both this projection and the context-integrity check entirely (finding 16, added in revision 2).**
- The new `context-budget` repair signature reuses the existing bounded repair loop rather than inventing a parallel retry policy.
- `authoritative_slice_entries()` is a genuine correctness improvement: `completed_slice_ids()` now honours the *latest* recorded outcome per slice, so a superseded pass no longer keeps a slice "complete".
- Validating the two ledgers for *every* result status (not just `pass`) is coherent: a considered `blocked` with a malformed ledger becomes a `result-malformed` repair (rewrite the same honest result), so knowledge is not silently lost — and `slice_entry_from_gate` sanitising malformed ledgers at persist time prevents run-state self-poisoning. Both behaviours are covered by tests.

**Findings:**

1. **[P2] `skills/project-manager/references/run-state-schema.md:281` — the signature taxonomy list is stale versus code.** The document (the declared source of truth for the run-state contract) says: "Repairable signatures are `validation`, `drift`, `review`, `reviewer-evidence`, `unauthorized-files`, `changed-files-mismatch`, `result-malformed`, `commit-missing`, `dirty-worktree`, and `developer-repairable`. Terminal `needs-human` signatures are `integrity-head` and `slice-id-mismatch`." The code (`gates.py:37-63`) additionally defines repairable `residual-ledger-mismatch` and `context-budget`, and terminal `reviewer-unavailable`; the runner additionally produces terminal `prior-context-integrity` and repairable `transient-service-unavailable` / `idle-no-progress`. This commit added `context-budget` to code and updated other doc sections but missed this list. Per CONTRIBUTING ("duplicated guidance is a defect even when the copies agree" — and worse when they don't), this specific list should be corrected, or replaced with a pointer to the taxonomy in `gates.py`.

2. **[P3] `skills/project-manager/scripts/pm_lib/gates.py:28-63` — the taxonomy frozensets claim an authority they don't fully have.** The comment declares `REPAIRABLE_SIGNATURES`/`TERMINAL_SIGNATURES` "the single source of truth for which violations are repairable versus terminal", but three signatures bypass them: `transient-service-unavailable` (runner.py:201), `idle-no-progress` (runner.py:754), and `prior-context-integrity` (runner.py:535) are constructed as `GateDecision`s directly rather than through `gate_failure()`. No behavioural bug — each is individually correct — but a future maintainer keying anything on those sets will miss three real signatures. Fix direction: register all signatures in the constants and route construction through `gate_failure()` (or soften the comment).

3. **[P3] `skills/project-manager/scripts/pm_lib/state.py:22` — cross-module private imports.** `state.py` imports `_continuation_notes_status` and `_residual_findings_status` (underscore-private) from `gates.py`. Related: the **continuation-note** validation rules exist twice in two dialects — return-a-string in `gates.py:593` and raise-`PmError` in `state.py:486` — with identical limits and category sets. *(Corrected in revision 2: residual-finding validation is not duplicated — `state.py` reuses the gates validator at persist time and run-state validation does not shape-check `residual_findings` at all; see finding 20.)* Fix direction: one public validator returning a reason string, wrapped by both callers.

4. **[P3] `skills/project-manager/scripts/pm_lib/state.py` (throughout) — the schema version is hand-embedded in ~60 error strings.** The bulk of this commit's `state.py` diff was mechanically rewriting `schema-v3` → `schema-v4` in error messages. Deriving the prefix once (e.g. `_ERR = f"invalid schema-v{SCHEMA_VERSION} run state"`) makes the next schema bump a one-line change and removes a whole class of missed-string drift.

5. **[Reclassified P2 in revision 2 — see finding 17] `skills/project-manager/scripts/pm_lib/runner.py:539-558` — the passing entry is built twice, and the two builds are *not* identical.** On a passing gate, `finalize_model_supervised_slice` builds a projected entry (`write_summary=False`) for the budget check, discards it, and `_finalize_terminal` rebuilds it. The original report called this "harmless functionally" — that was wrong: `_finalize_terminal` cancels reviewers and refreshes `reviewer-runs-summary.json` (`runner.py:467-469` → `runtime.py:1050-1087`) *between* the two builds, so the persisted entry's `audit_provenance` can differ from what the budget check (and the gate) saw, and `completed_at` regenerates (`state.py:944`). The race consequences are finding 17. Fix direction: snapshot once — build the entry a single time from the same evidence the gate verified, and cancel reviewers afterwards.

### `0b41986` — Archived finished plans

Removes two completed implementation-plan documents from git tracking, consistent with the repo's archive-don't-delete convention (`archive/` is local and gitignored; the documents remain recoverable from git history regardless). No findings.

---

## Part 2 — Holistic Review

### What is working well (worth preserving as-is)

- **The trust architecture largely matches the vision's claims.** *(Revision 2 tempers the original wording: findings 15–18 identify the places where it does not.)* Where I checked, the core mechanical guarantees are real: recomputed changed-file authorization with segment-aware matching (`git_ops.is_authorized_path`, deliberately `PurePosixPath.full_match` rather than `fnmatch`), commit ancestry and HEAD-advance checks on git evidence *before* comparing self-reported hashes (`gates.py:836-841`), artifact existence gated on real non-empty files *inside* the run directory (`artifact_exists`), a reviewer-evidence footprint that raises the cost of casual forgery (`gates.py:449-461` — see finding 18 for its precise limits), and controller-state mirroring in git metadata with tamper evidence. Equally important, most *heuristic* boundaries are labelled as such in the docs (dependency/license stops, the unledgered-findings shape check, pane-marker detection). This honesty discipline is rare and remains the repo's strongest asset — which is exactly why the gaps in findings 15–18 matter.
- **Comment quality.** Load-bearing comments consistently record *why* (the double-Enter tmux race, the status-line strip bug, the fail-open `startswith("no")` approval trap, persist-before-launch ordering). These comments are doing real safety work.
- **Fail-closed defaults verified in code**, not just documented: unclear approval flags block; bare harness names refuse to launch; unknown gate signatures raise; unknown run-state fields are rejected; malformed reserved-skill-sets do not silently disable the reservation.
- **Test discipline.** 300 tests across both suites, boundary-focused, with fake harnesses so no real CLI or network is needed; tmux-dependent tests self-skip. CI runs both suites plus compile checks on 3.13.
- **The atomic skills honour "atomic usefulness".** `commit` (31 lines), `code-simplifier` (42), `report` (70), `scoped-implementation` (78), `drift-audit` (90) are small, standalone, and harness-agnostic. The source-of-truth map in CONTRIBUTING is genuinely honoured: launchers each live in exactly one place, and `handoff` derives its resume prompt rather than restating it.

### Findings (ordered by severity)

6. **[P2] `skills/orchestrator/ai-reminder` — a 1,237-line executable Python utility lives entirely outside the quality gates.** It has no tests, is not in CI's compile check (`.github/workflows/ci.yml:37-38` covers only the three reviewer scripts), is not part of any skill contract, and is referenced exactly once (a one-line mention in `skills/orchestrator/README.md:27`). It duplicates domain knowledge that is maintained and tested elsewhere (tmux pane interaction, Codex/Claude transcript discovery — overlapping `reviewer_sessions.py`), so it *will* silently rot as those contracts evolve. This is the largest single simplification opportunity in the repo: either archive it, or promote it to a first-class tested tool (compile check + tests + a documented contract). Its current state — as large as all but one runtime module (1,237 lines vs `runner.py`'s 1,253 — revision 2 corrects the original "bigger than any" claim), zero verification — is inconsistent with everything else here. *(The independent reviewer would rate this P3 as maintenance debt with no runtime exposure; I keep P2 because functionally-superseded, unverified code is precisely what the run-supersession machinery elsewhere exists to prevent, and an archive decision is pending anyway.)*

7. **[P2] Duplicated external-side-effect prompt pattern — a one-source-of-truth violation in a safety control.** The same ~8-line regex for detecting "push / create PR / deploy / install dependency / license change" prompts exists verbatim twice: compiled as `EXTERNAL_SIDE_EFFECT_PROMPT_RE` in `tmux_adapter.py:60-68` (the send-time hard-prompt guard) and inline as `external_side_effect_pattern` in `runtime.py:337-344` (`extract_operational_hints`). These are two enforcement layers of the *same* stop condition; a pattern fix applied to one silently leaves the other stale. VISION principle 6 explicitly calls this shape a defect even while the copies agree. Fix direction: move the hard-prompt marker vocabulary (and this regex) into `constants.py` and import it in both places. (Smaller instance of the same shape: `LABEL_RE` is defined in `reviewer_jobs.py:60` even though the identical `reviewer_contract.LABEL_RE` is already imported at line 33.) *(The independent reviewer would rate this P3 because the send-time guard is independently enforced; I keep P2 — both copies feed operational guards, since hard-stop hints from `extract_operational_hints` also gate `send`/`pause-until`, so divergence would make the two guard layers disagree.)*

8. **[P3] `gates.py:221-355` vs `gates.py:358-544` — `reviewer_audit_provenance` and `reviewer_evidence_failure` duplicate a ~150-line pipeline.** Both walk `reviewer-runs-summary.json`, normalize manifest entries through `_normalized_reviewer_contract`, match status payloads by label, extract `skill_verdicts`, and pick the latest completion by `(finished_at, sequence)`. They differ only in bookkeeping (provenance record vs. ordered failure reasons). The parallel tuple shapes (`(finished_at, seq, tool, label, verdict)` vs `(finished_at, seq, verdict)`) are exactly the kind of thing that drifts. Fix direction: one shared generator yielding validated reviewer completions `(tool, label, audit, verdict, finished_at, seq)`, consumed by both.

9. **[P3] `runner.py` — the fresh-session relaunch block is duplicated (~60 lines).** `finalize_model_supervised_slice` (lines 658-722) and `handle_idle_stall` (lines 868-913) repeat the same sequence: force-stop, bump `session_generation`, mint a session id, build a relaunch adapter, write the fresh-session prompt, persist state *before* launching (a safety-ordering invariant currently documented in only one of the two copies), then launch with failure-evidence capture. Fix direction: extract one `_relaunch_fresh_session(...)` helper so the persist-before-launch rationale lives in exactly one place.

10. **[P3] `pm_lib/__init__.py` (342 lines) is a maintenance tax with one consumer.** It exists so `pm.py`'s `from pm_lib import *` gives the test suite `pm.<anything>` access. Every new helper now requires three edits (module, import block, `__all__`) — this commit's diff shows exactly that churn. The tests already import `pm_lib.runtime`, `pm_lib.state`, etc. directly for patching. Fix direction: migrate test references to the module imports they already use and shrink the facade to the CLI entry point, or generate the re-exports mechanically. Low urgency, steady payoff.

11. **[P3] `runtime.py` (1,184 lines) is a grab-bag module.** It contains at least five unrelated concerns: operational-hint extraction (a ~370-line regex engine), prompt/repair-template rendering, prior-slice-context generation and integrity, reviewer policy/credential plumbing, and artifact capture/cancel utilities. Each is individually fine; together they force every reader through unrelated code and invite import cycles (already worked around via `observation.py`'s module docstring). Fix direction when convenient: split into `hints.py`, `prompts.py`, `context.py`, keeping `runtime.py` as the residual.

12. **[Withdrawn in revision 2]** ~~`state.py:render_run_report` re-implements authoritative-entry selection.~~ The independent reviewer refuted this and I accept the refutation: the renderer must retain grouped superseded outcomes for its per-slice history sections, which `plan.authoritative_slice_entries()` deliberately discards, so direct reuse would not satisfy the renderer's requirements. The residual observation (the "latest entry wins" rule appearing in two places) is not worth an abstraction.

13. **[P3] `run-state-schema.md:368` — a single ~450-word paragraph enumerates every slice artifact.** This is the contract users are told to consult when auditing a run, and it is effectively unscannable. Converting it to a table or list would materially help the "auditable in minutes" promise of the unattended-operator story. Same document, same section (`:285`): one paragraph of ~500 words describes the entire two-path repair protocol.

14. **[P3] `commands.py:status` (lines 385-389) re-implements artifact-dir resolution** that `observation._slice_artifact_dir` already provides. Trivial, but it is the pattern (resolve `artifact_dir`, absolutize against repo) that must stay consistent for evidence lookup.

### Observed and accepted (no action needed, recorded for the avoidance of re-review)

- `slice_entry_from_gate` silently empties malformed ledgers when persisting *failure* entries — acceptable because the gate has already recorded the malformation in `gate_reason`, and persisting the malformed data would poison strict run-state validation on the next load.
- `utc_now`/`iso_now` and small helpers are duplicated between `pm_lib` and the orchestrator scripts — justified: the skills are contractually standalone (VISION principle 5), and the one deliberate cross-skill reuse (`reviewer_jobs_module()`) is explicit and documented.
- The budget projection only checks the immediate next slice; later slices are protected inductively (each acceptance checks the next launch) plus the fail-closed launch-time re-check. Correct as built **on the runner path** — the `reconcile` bypass is finding 16 (revision 2).
- `pause-until` counter updates read pre-lock values — safe under the documented one-controller assumption, which `run-state-schema.md:164-170` states candidly.

---

## Part 3 — Fitness Against the Vision and Personas

**The unattended operator (Rung 2).** Well served. The full chain is real: durable schema-v4 state with tamper detection, deterministic gates recomputed from git evidence, the bounded signature-keyed repair loop, operational recovery (rolling-window pause with hard-stop floors), per-slice evidence bundles, and now cross-session context continuity with provenance labels. The "supervision commands outlive tool-call limits" risk named in the vision has a concrete mitigations section (Long-Running Command Discipline) and an orphan-detection warning in `status`. The main friction is auditability-of-the-docs (finding 13) rather than auditability-of-the-evidence.

**The accountable engineer (Rungs 0–1).** Well served, and the vision's own risk — "ceremony must stay proportional" — is respected: the atomic skills are one explicit request each, the checkpointed Mode A launcher is a single copy-paste, and the README's situation→rung table gives the proportionality guidance directly. The plan format serves this persona without PM (batches, profiles, human checkpoints), exactly as the vision demands.

**The local-first engineer.** The structural supports the vision promises them are present and honest: validated launcher with embedded skill bundles (no native skill support needed), field-specific rejection feedback (`ContractIssue` with corrections), the repair loop for format slips, PM's recomputed mutation gates as the backstop when a harness's "read-only" is a suggestion (the per-harness enforcement facts are recorded factually in `REVIEWER_PROFILES` and the harness references, without ranking — principle honoured). Cold-start/silent-prefill guidance exists (`SKILL.md:121`). The privacy section's supervising-seat warning ("pane excerpts can include fragments of the code under work") is exactly the disclosure this persona needs.

**Principle-level check.** One source of truth: violated in the three places named above (findings 1, 7, and the taxonomy escape hatches of finding 2) and honoured everywhere else I checked. Honest threat model: consistently honoured — this is the repo's most distinctive strength. Trust the architecture, not the model: honoured in code, not just prose. Fail closed: verified at every layer I exercised.

---

## Part 4 — Independent Review (added in revision 2)

### Provenance

At the user's request, the draft report (frozen at SHA-256 `5f56e776…d253c9a`) was sent for independent review through the `orchestrator` skill's validated launcher:

- **Reviewer:** Codex CLI (`codex exec`), model `gpt-5.6-sol`, effort `high`, in Codex's **mechanical read-only sandbox** (`--sandbox read-only`) pinned to this repository.
- **Launch evidence:** `.orchestrator/runs/reviewers-20260716-180614-71616/` — validated schema-v2 launch contract (`status: pass`), request/policy/prompt/launch artifacts, process status `completed`, returncode 0, label `01-codex-review-report-r1`. A first attempt (`01-codex-review-report`) failed at model resolution (bare `sol` is not a valid model ID for this account); the corrected `-r1` request pinned `gpt-5.6-sol`. Both attempts are preserved in the run directory.
- **Task:** verify every numbered finding against the code, hunt for missed material defects (focused on `gates.py`, `runner.py`, `state.py`, `runtime.py`, and the orchestrator evidence chain), and assess severity calibration and the verdict.

**Reviewer summary (per orchestrator discipline):** the evidence was sufficient and high-signal — the reviewer confirmed 9 of 14 findings at my severity, correctly refuted 1, correctly reclassified 1, proposed 3 severity dissents (recorded inline at findings 6, 7, 18, 19), and surfaced 7 genuinely missed findings of which I verified and accepted all 7 (one at a higher severity than anything in my draft). Estimated share of the final report's material content: roughly a third of the defect findings. Every accepted claim below was re-verified by me against the code before inclusion; nothing was adopted on the reviewer's word alone.

### Codex's verdict challenge, and my resolution

The reviewer **disagreed with PASS WITH RISKS**, asserting two P1 trust-boundary defects. After verifying both in the code, I accept one as P1 (finding 15) and rate the other P2 (finding 16, reasons inline). The report's verdict is revised accordingly (see Verdict). The reviewer also identified factual errors in my draft — all verified and corrected inline in Parts 1–2 (findings 3, 5, 6, 12, the "trust architecture" bullet, and the schema-v4 layering claim).

### New findings (15–21), verified and adopted

15. **[P1] Opt-in independent-audit evidence is not bound to the slice attempt, repair round, or reviewed tree state.** The reviewer policy PM writes contains no `before_head`, attempt, or session generation (`runtime.py:528-546`), so its JSON — and therefore its SHA-256 — is *identical* across attempts and repair rounds of the same slice. Launch contracts from a superseded attempt still match the current policy digest (`gates.py:182-184`), `capture_reviewer_runs_summary` sweeps every historical run directory under the slice (`runtime.py:1024-1047`), and latest-PASS selection keys on `finished_at` alone (`gates.py:524-543`). Consequence: on a slice marked `Independent audit required: yes`, a Reviewer `PASS` obtained *before* a tree-changing repair (an `unauthorized-files` restore or a `dirty-worktree` cleanup — both ordinary, fully unattended repair signatures) satisfies the mechanical gate for final work the Reviewer never saw. The guarantee the opt-in exists to provide degrades to prompt-enforced sequencing exactly where the plan asked for mechanical proof, and `run-state-schema.md:461`'s claim that evidence must cover the slice "before it will accept a pass" is not what the code enforces. **Fix direction (small):** include `before_head` and the repair `session_generation`/round in `reviewer-policy.json` and rewrite it (plus the `current_slice.reviewer_policy` snapshot) at each repair round — stale launch contracts then fail the existing digest match with no new gate logic; optionally also require each audit's `finished_at` to postdate the last tree-changing repair. *(Reviewer: P1. I concur: it contradicts a documented mechanical guarantee on the highest-stakes slices and is reachable unattended.)*

16. **[P2] `reconcile` accepts a stopped slice without re-running the prior-context integrity or context-budget checks.** `commands.py:966` runs only `verify_gate`; the two runner-path checks (`runner.py:533-558`) are absent, and terminal slice entries do not retain `prior_slice_context` metadata (`state.py:381-404`), so the digest could not be re-verified at reconcile time even if the check existed. Two consequences: (a) a run stopped terminal for `prior-context-integrity` — a breach the documentation says is *never steered, only stopped* — can be flipped to `pass` by `reconcile` with no re-verification and no recorded waiver; (b) an oversized reconciled result skips the budget projection and wedges the next launch at `write_prior_slice_context` (`runtime.py:742-747`) — fail-closed, but recoverable only via re-`init --assume-complete`, which discards the accumulated continuation history. `SKILL.md:207`'s claim that `reconcile` applies "the same strict reconciliation criteria" is currently untrue. **Fix direction:** persist `prior_slice_context` metadata into slice entries, make `reconcile` run both checks, or explicitly define `reconcile` as a recorded operator waiver (with an audit-trail entry saying which checks were waived). *(Reviewer: P1. I rate P2: the path requires an explicit operator command on an already-stopped run — a human is definitionally in the loop — and the budget half fails closed downstream. The documented-guarantee mismatch is real either way and must be fixed at least in the docs.)*

17. **[P2] Verification/finalization race on reviewer verdicts.** `finalize_model_supervised_slice` snapshots `reviewer-runs-summary.json` and verifies the gate (`runner.py:531-537`); `_finalize_terminal` then cancels reviewers and *refreshes* those summaries (`runner.py:467-469` → `runtime.py:1050-1087`) before `slice_entry_from_gate` recomputes `audit_provenance` — without re-running the gate. A reviewer that completes adversely in that window becomes the durable "latest" verdict while the slice records `pass`/"all gates passed", and the persisted provenance can differ from what the gate verified (this is why original finding 5's "harmless" was wrong). `reconcile` similarly accepts without cancelling in-flight reviewers (`commands.py:961-983`). **Fix direction:** take one snapshot; verify, build the entry, and persist from that same snapshot; cancel reviewers afterwards.

18. **[P3] The reviewer-evidence "real process footprint" is weaker than the schema doc implies.** `_normalized_reviewer_contract` checks a positive-integer `pid` and the existence of out/err files under the artifact root (`gates.py:197-207`); it does not check process identity, the status file's recorded `child_identity`/CWD (`reviewer_jobs.py:1122-1157`), or the manifest's command. That is *consistent* with the declared threat model (VISION explicitly excludes a determined adversary fabricating coherent evidence), but `run-state-schema.md:461`'s "backed by a **real** positive subprocess pid and **real** outfile/errfile" overclaims what is verified — and per CONTRIBUTING, overclaiming is a defect. **Fix direction:** correct the doc wording, or cheaply strengthen the check by matching the status file's `child_identity`. *(Reviewer: P2. I rate P3 given the documented threat model; my own draft's "cannot forge delegation" phrasing had the same overclaim and is corrected in Part 2.)*

19. **[P3] Repair-round ledger retention is prompt-enforced only.** Archived `developer-result-repair-*.json` ledgers are re-injected into fresh-session prompts as instructions (`runner.py:963-1013`), but no gate compares the fresh result's `residual_findings`/`continuation_notes` against the archived items (`gates.py:737-742` validates shape only), so a repair round can silently drop knowledge. A mechanical superset check would be cheap. *(Reviewer: P2. I rate P3: loss degrades continuation knowledge but cannot corrupt acceptance, and the retention requirement is stated in prompt text rather than claimed as mechanical anywhere in the docs.)*

20. **[P3] Run-state validation leaves several slice-entry fields shape-unchecked.** `state.py:686-711` validates status, repair, provenance, reviewer tools, continuation notes, and per-status commit-hash/artifact fields — but not `summary`, `changed_files`, `validation`, the `drift_audit`/`code_review` records, `commit`, `blockers`, `next_action`, `residual_findings`, or timestamps. Given the schema's otherwise strict reject-unknown-fields posture, either extend validation or document the boundary.

21. **[P3] `reviewer_jobs.py wait` can exit 0 for a wrapper that died before writing its status file.** `reviewer_status` yields `returncode=None`/state `"finished"` for a dead wrapper with no status (`reviewer_jobs.py:389-412`), and `command_wait` treats only non-`None` nonzero return codes as failure (`reviewer_jobs.py:958-971`). PM's evidence gate still rejects such a run (no `completed`/returncode-0 status), so the impact is a misleading helper exit code, not an acceptance hole. Fix: treat missing-status-plus-dead-wrapper as failed.

### Reviewer claims I did not adopt as written

- **Severity dissents** at findings 6, 7 (reviewer: P3; I keep P2) and 16, 18, 19 (reviewer: P1/P2/P2; I rate P2/P3/P3) — reasons recorded inline at each finding. These are judgment calls, and both positions are preserved so the maintainer can overrule either way.
- The reviewer's open question — whether `reconcile` is *intended* as an operator waiver — is adopted into Open Questions below rather than resolved unilaterally.

---

## Recommended Action List (in priority order)

1. **Fix finding 15 (P1):** bind `reviewer-policy.json` to `before_head` and the repair round/session generation, refreshing the policy and its `current_slice.reviewer_policy` snapshot per round, so stale Reviewer launch contracts fail the existing digest match. This is the one blocking item.
2. **Fix finding 16:** persist `prior_slice_context` metadata in slice entries and make `reconcile` run the context-integrity and budget checks (or define and record explicit waiver semantics); correct `SKILL.md:207` in the same change.
3. **Fix finding 17:** in `finalize_model_supervised_slice`/`_finalize_terminal`, verify, build, and persist the slice entry from one reviewer-summary snapshot, and cancel reviewers afterwards (this also resolves reclassified finding 5).
4. Fix the stale signature-taxonomy list in `run-state-schema.md` (finding 1) and, in the same doc pass, correct the "real process footprint" overclaim (finding 18) — cheap drift fixes in a declared source-of-truth contract.
5. Deduplicate the external-side-effect regex into `constants.py` (finding 7) — cheap, safety-relevant.
6. Decide `ai-reminder`'s status: archive it or bring it under test/CI (finding 6).
7. Route all gate signatures through the taxonomy sets / `gate_failure()` (finding 2).
8. Unify the continuation-note validator shared by `gates.py` and `state.py`, and de-privatize the imports (finding 3).
9. Derive the schema-version error prefix from `SCHEMA_VERSION` (finding 4).
10. Extract the shared relaunch helper in `runner.py` (finding 9) and the shared reviewer-completion iterator in `gates.py` (finding 8) — the latter is also where the finding-15 and finding-17 fixes will land, so consider doing them together.
11. Add the mechanical repair-round ledger superset check (finding 19) and the `wait` exit-code fix (finding 21) when convenient.
12. Opportunistic, next time each file is touched: split `runtime.py` (11), shrink `__init__.py` (10), reuse `_slice_artifact_dir` in `status` (14), reformat the two mega-paragraphs in `run-state-schema.md` (13), and extend or document run-state field validation (20).

Items 4–10 are behaviour-preserving; items 1–3 deliberately change gate behaviour (strictly tightening it) and so deserve their own plan slices with tests pinned beside them.

---

## Coverage Summary

- **Scope reviewed:** commits `dc0aa25`, `9774f49`, `0b41986` (full diffs); all 16 `pm_lib` modules + `pm.py`; all 3 orchestrator scripts; all 10 skill `SKILL.md` files; all references (`run-state-schema.md`, `developer-prompt.md`, `harness-adapter-contract.md` headings, `pm-slice-contract.md`, `reviewer-contract.md` and per-harness refs by index, `templates.md` by index); `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md` (by diff), `docs/VISION.md`, CI workflow, gitignores. `archive/` excluded per instruction.
- **Requirements checked against:** `docs/VISION.md` (personas, principles, non-goals), `CONTRIBUTING.md` source-of-truth map and change conventions, and the documented contracts in the references.
- **Dimensions checked:** correctness, boundary/invalid input, state/lifetime (locks, atomic writes, process tracking), interfaces/data contracts (schema v4 code↔doc), concurrency assumptions, security/robustness (path containment, forgery resistance, credential handling), tests, observability, maintainability, documentation.
- **Validation run:** both unittest suites (300 tests, all green). Not run: any live harness/tmux end-to-end run beyond the suites' fake-harness runtime tests. One real reviewer CLI launch was performed for Part 4 (Codex `gpt-5.6-sol`, read-only sandbox, via the orchestrator validated launcher; evidence in `.orchestrator/runs/reviewers-20260716-180614-71616/`).
- **Independent review:** performed by a second model (Part 4); all adopted claims re-verified against the code by the author. Audit provenance for this report: authored by Claude (Fable 5) with a delegated Codex reviewer; final judgments are the author's.
- **Drift-audit status:** no frozen contract governs this review request (it is a standalone Rung-0 review), so no drift-audit gate applies.

## Open Questions / Assumptions

- Finding 6 assumes `ai-reminder` is not quietly relied on elsewhere; only one README mention was found. If it is in active personal use, "promote to tested tool" is the right branch rather than archive.
- I did not attempt to falsify the tmux TUI timing claims (double-Enter race, readiness banners); they are documented as reproduced and tests cover the adapter mechanics with fakes.
- Is `reconcile` *intended* as an explicit human waiver of terminal integrity stops? (Raised by the independent reviewer.) The docs describe it only as re-running "the same strict" gates and it records no waiver or attestation. If waiver semantics are intended, they need an explicit contract and an audit-trail record; if not, finding 16's mechanical fix is required.
