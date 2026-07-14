# Implementation Plan: Orchestrator Skill and Role Migration

## Objective

Rename the `ai-orchestrator` skill to `orchestrator`, rename the primary agent role from Orchestrator to Developer, collapse Senior worker and Junior worker into one read-only Reviewer role, and carry the new vocabulary and authority boundaries through every active runtime, schema, CLI, test, skill, and current document in this repository. This is a clean break: no compatibility aliases or fallback paths, schema migration, deprecated flags, or compatibility shims will remain. The deliberate Developer self-audit path for default slices is current workflow behaviour, not backward compatibility.

This plan is anchored in `docs/VISION.md`: contracts remain frozen before code, authorization remains separate from quality, evidence remains stronger than narration, and the constant chain remains plan → scoped implementation → validation → drift audit → code review → commit. The rename must clarify ownership without weakening any gate.

## Frozen Terminology and Behaviour

- `orchestrator` is the skill and workflow name, not an actor role.
- Developer is the context-rich primary agent. It owns session management, planning, coding, validation, semantic verification of Reviewer output, gate decisions, commits, and the final deliverable. Under Master Controller it is the per-slice Developer and holds no authority above MC.
- Reviewer is the only delegated role. It is read-only and may gather evidence, map code, investigate, perform drift audits, and perform code reviews. It never edits files, performs Git/GitHub mutations, commits, accepts drift, makes final gate decisions, or re-delegates.
- Reviewer requests contain the task, selected tool/model/effort, files/context, required skills, constraints, and output contract. Callers cannot choose role or access. The launcher owns the constants, and normalized evidence records `role: "reviewer"` and `access: "read-only"` for every accepted launch.
- A Developer may self-audit when no Reviewer is configured, when Reviewer execution is unavailable on a default slice, or when the launcher selects self-audit. The slice summary, run report, and summary output must explicitly identify each audit as Reviewer-performed or `developer-self-audit` and include Reviewer tool/label evidence or fallback context. `Independent audit required: yes` still requires distinct validated Reviewer runs for drift audit and code review in that order.
- All test execution remains with the Developer. A Reviewer may inspect test code and existing results, but it does not run suites because tests commonly create caches, snapshots, or generated files.
- Claude, Codex, Copilot, and OpenCode are equally eligible as Developer or Reviewer. The user selects the right harness and model through the plan or launcher; no capability ranking, default-role ranking, role allow-list, or role-suitability gate remains.
- Harness profiles document the factual strength of read-only enforcement, including prompt-only or partial enforcement. These facts never disqualify a supported harness from Reviewer use. The Reviewer contract remains read-only, and under MC the deterministic changed-file and clean-worktree gates remain the mutation backstop.
- Existing `.ai-orchestrator/` runtime state is archived under the repository's ignored `archive/` tree before the ignore rule is removed. It is never loaded, renamed into active state, or migrated. New runs start under `.orchestrator/` with the new schema.
- Active source and current documentation adopt the new vocabulary. Historical changelog entries, archived snapshots, dated `mc-test` reports, and generated run evidence retain the exact names that were true at the time; this is historical accuracy, not backward compatibility.
- The human persona currently called “the accountable developer” becomes “the accountable engineer” so capitalized Developer remains unambiguous as an agent role.

## Review Findings and Approval Decisions

The following decisions resolve the workflow consequences that do not follow from string replacement:

1. The role collapse intentionally removes delegated coding, refactoring, surgical edits, Git/GitHub operations, commit mechanics, and write-capable test work. The Developer absorbs all of that work.
2. Reviewer independence remains a degradable preference on default slices to preserve the autonomy ladder described by the vision. Making a Reviewer mandatory for every drift audit and code review would be a separate workflow-policy change affecting cost, privacy, local-only operation, preflight, and all fixture plans.
3. Every supported harness and model is equally eligible for either role. Harness-specific enforcement differences are informational and never become selection policy.
4. Reviewer role and access are launcher-owned constants, not caller-selectable request fields. Normalized evidence still records both values.
5. Every public role-shaped identifier is included in the clean break: skill path/frontmatter, helper modules, policy/request names, environment variables, state directories, CLI flags, JSON fields, manifest keys, artifact filenames, prompt/result names, failure signatures, exported Python names, tests, and documentation.
6. Master Controller state/result schema advances from version 2 to version 3, and the Reviewer contract schema advances from version 1 to version 2. Old runs and requests fail closed and must be reinitialized.

## Implementation Profiles

- Recommended for a frontier/senior implementer: complete Slice 1 as one atomic breaking-contract migration, obtain an independent drift audit and code review, then complete Slice 2.
- Recommended for a standard implementer: still keep Slice 1 atomic because splitting the package move from Master Controller consumers leaves the repository intentionally broken; use frequent targeted tests inside the slice.
- Do not use Master Controller Mode B to modify its own live role/schema contract. Use Mode A checkpointed execution with an independent read-only Reviewer or subagent for the authorization and quality passes.

## Slice Batches

- Batch A: Slice 1 only — the skill package, Reviewer launcher, Master Controller consumers, schemas, CLI, artifacts, and tests form one indivisible breaking contract.
- Batch B: Slice 2 only — current prose and dependent skills are updated after the executable vocabulary is stable.

## Slice 1: Migrate the Executable Role Contract

### Intended Change

- Move `skills/ai-orchestrator/` to `skills/orchestrator/` and set the skill frontmatter name to `orchestrator`.
- Rename the worker contract, job/session helpers, tests, references, classes, functions, constants, prompts, schemas, manifests, artifacts, state directory, and environment variables to Reviewer terminology.
- Remove `workspace-write`, Senior worker, Junior worker, delegated implementation, delegated Git/GitHub mutations, and other write-capable Reviewer paths from executable policy and tests.
- Remove role/access from caller requests; stamp exact Reviewer/read-only values into normalized launch evidence and remove redundant policy allow-lists.
- Remove capability tiers, default-role rankings, role allow-lists, and suitability checks so every supported harness can be selected for either role.
- Migrate Master Controller from slice Orchestrator/worker terminology to slice Developer/Reviewer throughout prompt rendering, state, gates, repair, observation, cancellation, summaries, exports, and harness profiles.
- Rename `--worker-tools`, `--worker-model`, and `--worker-effort` to `--reviewer-tools`, `--reviewer-model`, and `--reviewer-effort`; rename all persisted fields and artifact names with no aliases.
- Rename `orchestrator-result.json`, transcript artifacts, prompt references, status constants, and repair signatures to Developer equivalents.
- Record evidence-backed drift-audit and code-review provenance in every terminal slice entry, slice summary, run report, and `summarize` output, including mixed Reviewer/Developer outcomes and explicit self-audit fallback context.
- Bump breaking schemas, reject old shapes, and update security/regression tests to prove the old roles and write access cannot launch or pass gates.
- Archive the ignored live `.ai-orchestrator/` tree before replacing its ignore rule with `.orchestrator/`; do not migrate its contents.
- Update continuous integration to compile and test the renamed modules and paths.

### Acceptance Criteria

- Inputs:
  - Current `skills/ai-orchestrator/` skill and schema-v1 worker contract.
  - Current Master Controller schema-v2 state/result contract and old CLI/artifact vocabulary.
  - Clean parent repository worktree and the ignored legacy `.ai-orchestrator/` runtime tree.
- Outputs:
  - `skills/orchestrator/` is the only active skill path and `name: orchestrator` is the only active skill identifier.
  - Reviewer launcher code accepts schema-v2 requests without caller-owned role/access fields, stamps Reviewer/read-only normalized evidence, and rejects old schemas, old fields, old roles, and every write request.
  - Every supported harness is selectable for either role; enforcement notes remain informational and no profile ranking or suitability gate rejects the selection.
  - Master Controller schema v3 uses Developer/Reviewer names consistently in CLI, state, prompts, artifacts, gates, summaries, profiles, and Python exports.
  - `.orchestrator/` is the only active local runtime state path; legacy runtime data exists only in ignored archive storage.
  - CI and both executable test suites use the new paths and pass.
- User-visible behaviour:
  - Users invoke the `orchestrator` skill and configure Reviewer tools with `--reviewer-*` flags.
  - The Developer performs all coding and session management; Reviewers are visibly and mechanically constrained to the read-only contract supported by each harness.
  - Existing runs/requests using old schemas or names fail closed with an actionable reinitialize/recreate message.
  - Slice summaries, run reports, and summaries always state whether drift audit and code review came from validated Reviewer evidence or Developer self-audit, with tool/label or fallback context.
- Behaviour that must not change:
  - The constant engineering chain and the ordering of drift audit before code review.
  - MC's deterministic file authorization, commit ancestry, clean-worktree, evidence-consistency, repair-budget, and stop-for-human gates.
  - Reviewers own no gate or acceptance authority and never commit or re-delegate.
  - Default slices may still use local Developer audits; opt-in independent slices still require separate exact-PASS drift-audit and code-review evidence.
  - Vendor transcript fields such as external JSON `role: "assistant"` remain untouched because they are vendor schemas, not repository roles.

### Authorized Surface

- Files allowed to change:
  - `.github/workflows/ci.yml`
  - `.gitignore`
  - `skills/ai-orchestrator/` (renamed source tree)
  - `skills/orchestrator/` (renamed destination tree)
  - `skills/master-controller/AGENTS.md`
  - `skills/master-controller/README.md`
  - `skills/master-controller/SKILL.md`
  - `skills/master-controller/references/harness-adapter-contract.md`
  - `skills/master-controller/references/orchestrator-prompt.md` (renamed source)
  - `skills/master-controller/references/developer-prompt.md` (renamed destination)
  - `skills/master-controller/references/run-state-schema.md`
  - `skills/master-controller/scripts/mc_lib/__init__.py`
  - `skills/master-controller/scripts/mc_lib/cli.py`
  - `skills/master-controller/scripts/mc_lib/commands.py`
  - `skills/master-controller/scripts/mc_lib/constants.py`
  - `skills/master-controller/scripts/mc_lib/gates.py`
  - `skills/master-controller/scripts/mc_lib/models.py`
  - `skills/master-controller/scripts/mc_lib/observation.py`
  - `skills/master-controller/scripts/mc_lib/profiles.py`
  - `skills/master-controller/scripts/mc_lib/runner.py`
  - `skills/master-controller/scripts/mc_lib/runtime.py`
  - `skills/master-controller/scripts/mc_lib/state.py`
  - `skills/master-controller/scripts/mc_lib/tmux_adapter.py`
  - `skills/master-controller/tests/mc_test_helpers.py`
  - `skills/master-controller/tests/test_gates_verification.py`
  - `skills/master-controller/tests/test_harness_adapters.py`
  - `skills/master-controller/tests/test_observation_hints.py`
  - `skills/master-controller/tests/test_plan_state.py`
  - `skills/master-controller/tests/test_prompts.py`
  - `skills/master-controller/tests/test_runtime_batch.py`
  - `skills/master-controller/tests/test_supervision_repair.py`
- Functions/classes/components allowed to change:
  - All role, policy, request, profile, prompt, process-tracking, transcript, artifact, state-schema, gate, repair, summary, and export components in the authorized skill trees.
  - No authorization matcher, plan parser, Git evidence algorithm, or generic process helper may change except for necessary renamed imports/messages.
- Tests allowed or expected to change:
  - Renamed orchestrator-skill contract/session tests.
  - Every Master Controller test that pins role lists, CLI/state fields, prompt/result filenames, Reviewer evidence, profile support, repair signatures, or legacy-schema rejection.

### Explicit Non-Goals

- No compatibility aliases, deprecated flags, dual-read schemas, symlinks, fallback import paths, or migration of active old run state.
- No changes to the constant gate chain, authorization matching semantics, plan syntax, Git algorithms, repair budgets, or commit policy.
- No new Reviewer sandbox implementation beyond the tested capabilities of the existing harnesses; enforcement differences are documented, not normalized or ranked.
- No rewrite of historical changelog entries, archive snapshots, dated test reports, generated artifacts, or vendor-owned transcript schemas.
- No commit, push, branch creation, plugin reinstall, or external catalog mutation in this slice.

### Risk Flags

- Risky surfaces touched:
  - Public CLI flags, JSON schemas, durable state, artifact names, environment variables, dynamic module paths, prompt contracts, role permissions, CI paths, and Master Controller gates.
- Approval needed before implementation: yes
- Independent audit required: yes

### Validation Plan

- Tests to add/update:
  - Reviewer contract tests that accept schema-v2 requests without role/access, stamp normalized `reviewer`/`read-only` evidence, and reject old roles, caller-owned role/access, old schemas, old fields, and every write path.
  - Profile tests proving Claude, Codex, Copilot, and OpenCode are all eligible Reviewers, while each harness's enforcement description remains factual and informational.
  - MC schema-v3 tests rejecting schema-v2 state/results and validating Developer/Reviewer state, prompts, artifacts, summaries, repairs, and exports.
  - Gate tests retaining all forged-evidence, wrong-tool, wrong-model, wrong-repository, wrong-skill, missing-verdict, non-PASS, unauthorized-file, commit, and clean-worktree protections under Reviewer names.
  - Provenance tests covering Reviewer execution for both audits, Developer self-audit with no Reviewer configured, Reviewer launch failure followed by allowed self-audit, mixed outcomes, independent-audit rejection of self-audit, and unconditional report/summary attribution.
- Commands to run:
  - `python3 -m py_compile skills/orchestrator/scripts/reviewer_contract.py skills/orchestrator/scripts/reviewer_sessions.py skills/orchestrator/scripts/reviewer_jobs.py`
  - `python3 -m unittest discover -s skills/orchestrator/tests -p 'test_*.py'`
  - `python3 -m py_compile skills/master-controller/scripts/mc.py skills/master-controller/scripts/mc_lib/*.py`
  - Delegate `python3 -m unittest discover -s skills/master-controller/tests -p 'test_*.py'` to a test subagent if it exceeds one minute; capture the exit code and concise pass/fail summary.
  - `python3 skills/master-controller/scripts/mc.py profiles`
  - `python3 skills/master-controller/scripts/mc.py --help`
  - `git diff --check`
  - Run a targeted active-surface search for `ai-orchestrator`, `senior-worker`, `junior-worker`, role-shaped `orchestrator_*`, and `worker_*`; require zero unexplained hits outside the migration plan and explicit historical allow-list.
- Manual checks:
  - Confirm `git status --short` represents the skill/package and prompt/helper/test renames as moves where Git can detect them.
  - Confirm the archived legacy runtime tree is ignored, inert, and no `.ai-orchestrator/` path remains active.
  - Inspect generated Reviewer policy/request/prompt/status artifacts and Developer result/prompt/transcript artifacts for consistent names and read-only semantics.
  - Confirm Reviewer output remains advisory evidence and the Developer/MC retain their existing gate authority.

### Rollback Path

- Before any commit, reverse the coordinated moves and code edits together; do not leave the repository between the old and new path contracts.
- If a committed rollback is later required, create a new revert commit after user approval. Never amend or restore old compatibility paths alongside the new ones.
- Preserve the archived `.ai-orchestrator/` evidence as historical data; rollback may restore the old software contract but must not silently reactivate or rewrite archived state.

## Slice 2: Align Vision, Dependent Skills, and Current Documentation

### Intended Change

- Rewrite the active role vocabulary in the vision, root README, contributing guide, changelog, implementation-plan launchers, scoped-implementation guidance, handoff schema/examples, commit guidance, and report guidance.
- Rename the human “accountable developer” persona to “accountable engineer.”
- Remove every dependent workflow that delegates edits, commits, Git/GitHub operations, or mutation-prone long-running tests to the Reviewer.
- Update all active links, commands, paths, and examples to `orchestrator`, Developer, Reviewer, `.orchestrator/`, renamed helper/artifact names, and `--reviewer-*` flags.
- Add an Unreleased breaking-change note without rewriting historical changelog entries.

### Acceptance Criteria

- Inputs:
  - The passing executable vocabulary and schemas from Slice 1.
  - Current active repository prose and dependent atomic skills.
- Outputs:
  - Every current source-of-truth document and dependent skill describes the same Developer/Reviewer authority boundary as the executable contract.
  - All links and example commands resolve to the renamed skill, prompt, contract, helper, test, CLI, state, and artifact paths.
  - Historical release/archive material remains factual and unchanged except for a new current changelog entry.
- User-visible behaviour:
  - Plan launchers tell the Developer to keep implementation and tests local and use Reviewers only for read-only evidence, drift audit, and code review.
  - Handoffs record Developer state and Reviewer runs; commit guidance never suggests Reviewer mutation.
  - The vision names the system roles without colliding with the human persona.
- Behaviour that must not change:
  - Atomic skills remain independently usable.
  - User approval remains mandatory before commits under the repository instructions.
  - Mode A/Mode B definitions, approval gates, audit ordering, and historical evidence remain intact.

### Authorized Surface

- Files allowed to change:
  - `CHANGELOG.md`
  - `CONTRIBUTING.md`
  - `README.md`
  - `docs/VISION.md`
  - `skills/commit/SKILL.md`
  - `skills/handoff/SKILL.md`
  - `skills/implementation-plan/SKILL.md`
  - `skills/report/SKILL.md`
  - `skills/scoped-implementation/SKILL.md`
- Functions/classes/components allowed to change:
  - Active prose, tables, examples, launchers, file links, and role-specific guidance only.
- Tests allowed or expected to change:
  - No executable tests are expected beyond documentation/path validation and plan parsing.

### Explicit Non-Goals

- No runtime, CLI, schema, or test changes from Slice 1.
- No rewriting of historical changelog entries or anything under `archive/`.
- No changes to `code-review`, `drift-audit`, or `code-simplifier`; their generic senior-quality wording is not a retired role name.
- No changes to `mc-test` in this repository slice; the nested repository has its own companion plan.
- No commit, push, or branch creation.

### Risk Flags

- Risky surfaces touched:
  - Authoritative vision and cross-skill workflow launchers.
- Approval needed before implementation: no
- Independent audit required: no

### Validation Plan

- Tests to add/update:
  - None.
- Commands to run:
  - `python3 skills/master-controller/scripts/mc.py check-plan --repo . --plan docs/implementation-plan-orchestrator-role-migration.md`
  - `git diff --check`
  - Validate every Markdown link/path changed in this slice exists after Slice 1.
  - Search active non-historical files for retired skill/role/helper/CLI/artifact names and classify any remaining occurrence explicitly.
- Manual checks:
  - Read the updated Roles and Design Principles sections in `docs/VISION.md` as a coherent whole, not isolated replacements.
  - Compare the implementation-plan Mode A launchers, scoped-implementation guidance, handoff template, and commit skill against the frozen role contract.
  - Confirm historical entries still identify the literal names used by old releases.

### Rollback Path

- Revert this documentation/skill-guidance slice independently if wording is unclear; Slice 1's executable contract remains valid.
- Any committed rollback requires a new user-approved revert commit; never amend.

## Companion Repository Plan

After both parent-repository slices pass, execute `/Users/dcroton/Documents/AI/repos/ai-engineering-skills/mc-test/docs/implementation-plan-developer-reviewer-fixtures.md` against the nested `mc-test` Git repository. Do not combine its diff, validation, staging, or commit with this repository.

## Next Chat Prompt

```text
Plan file: /Users/dcroton/Documents/AI/repos/ai-engineering-skills/docs/implementation-plan-orchestrator-role-migration.md
Slices this session: Slice 1 only.

Read the full plan file first. Work on the current branch; do not create or switch branches. Confirm both the parent repository and nested mc-test repository status before changing anything, but change only the parent repository in this session.

Use the orchestrator skill as the controlling workflow once the package rename is in place; until then, follow the frozen contract directly. Restate the authorized surface and non-goals. Stop for my approval because Slice 1 is approval-gated. The decisions are frozen: every supported harness is eligible for either role, enforcement differences are informational, and default Developer self-audit is valid but must be reported explicitly.

After approval, apply scoped-implementation to Slice 1. Archive the ignored legacy .ai-orchestrator runtime tree under archive/ without migrating it. Implement the entire breaking contract atomically, then run the targeted validation. Delegate any full test suite expected to exceed one minute to a test subagent and return only its exit code and concise summary.

Apply drift-audit against the frozen Slice 1 contract and report the authorization verdict before quality review. Then apply code-review independently. Fix findings inside the contract and repeat the relevant gates until they pass or stop if resolution requires scope expansion.

Do not commit, stage, push, reinstall external skills, or continue to Slice 2. Ask me before any commit and end with a concise handoff.
```
