# Steer-Artifact §6.6 Assessment

**Question:** Does the persistent `steer-<attempt>.md` family conform to Mode B Lite's approved artifact model, and if not, what is the narrowest compliant remediation?

**Assessment source:** independent Codex `gpt-5.6-sol`, xhigh effort, Reviewer-performed under the orchestrator's mechanically read-only sandbox. Launch and raw output are retained in `.orchestrator/runs/reviewers-20260719-232650-3292/` (`01-codex-steer-artifact-assessment-*`). The Reviewer read the listed governing reports, PM code, operating docs, tests, and directly relevant downstream consumers; it ran no tests and made no changes.

## Conclusion

**VIOLATION.** The current `finalize --steer` implementation creates a persistent, attempt-numbered, content-bearing correction prompt in both the controller state directory and the `.pm/` mirror, then instructs the Developer to read that prompt before continuing. This is a per-round repair-prompt family, which the target design and replacement ledger explicitly remove. The fixed delivery pointer is also an inline prompt fragment rather than reference-template-sourced text.

This is a narrow artifact-model conformance defect. The surrounding Lite mechanisms remain conformant: there is no second state copy, verdict parsing, failure taxonomy, unread-field schema machinery, or Developer-side ledger.

## Confirmed evidence

- `finalize --steer` increments the persisted attempt count, constructs `slices/slice-NNN/steer-<attempt>.md`, writes an authoritative controller original, mirrors it into `.pm/`, and sends the Developer a pointer to read it: [slice_ops.py](../../skills/project-manager/scripts/pm_lib/slice_ops.py:1136), [slice_ops.py](../../skills/project-manager/scripts/pm_lib/slice_ops.py:1156).
- The resulting artifact is a recovery input, not merely passive evidence: the Developer receives `PM correction written to <mirror> — read it before continuing.` [slice_ops.py](../../skills/project-manager/scripts/pm_lib/slice_ops.py:1160).
- Only launch-scoped `attempt-<n>/` rotation of stale result/pane evidence is allowed: [target-design.md](target-design.md:209).
- The governing design explicitly removes per-round repair prompts and replaces their history with events plus assessment narrative: [target-design.md](target-design.md:211), [replacement-ledger.md](replacement-ledger.md:77).
- The event currently retains only a truncated first line and points back to the steer file; assessments read that event note, not the artifact body. Thus deleting the file without changing event handling would lose correction detail: [slice_ops.py](../../skills/project-manager/scripts/pm_lib/slice_ops.py:1164), [slice_ops.py](../../skills/project-manager/scripts/pm_lib/slice_ops.py:1207).

## Required remediation

Implement this as **code-level conformance work**; no blueprint §8 report amendment is required.

1. Add a steer-message template section to [developer-prompt.md](../../skills/project-manager/references/developer-prompt.md). It must state that the correction remains within the frozen contract and cannot expand authorization, followed by `{correction}`.
2. Add `render_steer_message(correction)` to [prompts.py](../../skills/project-manager/scripts/pm_lib/prompts.py), loading the fixed wrapper from the reference document.
3. Add a multi-line, direct tmux-buffer injection helper in [sessions.py](../../skills/project-manager/scripts/pm_lib/sessions.py). It must preserve the existing liveness and hard-stop refusal behavior and use the established paste/double-submit discipline; it must not create a persistent correction file.
4. In [slice_ops.py](../../skills/project-manager/scripts/pm_lib/slice_ops.py), retain the existing token, session, risk-ratchet, attempt, and budget-exhaustion checks. Replace the numbered artifact write and pointer delivery with rendered direct injection. Append one `steer` event containing the complete correction in `note`, with no `evidence` path. Update assessment formatting so multiline corrections remain legible. Remove `SteerOutcome.steer_path`.
5. In [cli.py](../../skills/project-manager/scripts/pm_lib/cli.py), stop printing a correction-artifact path; report delivery and the persisted attempt number instead.
6. Update tests to prove: the wrapper is reference-sourced; the live pane receives the full multiline correction; no `steer-*.md` exists in controller or mirror artifacts; attempt/budget/hard-stop/dead-session behavior remains unchanged; and accepted/stopped assessments retain the full correction narrative.

## Boundary and downstream impact

The change must not alter run/slice statuses, the attempt budget, mechanical floor, risk ratchet, review freshness, HMAC/token authority, Developer `result.json`, command surface, or Stage 7 intervention counting. No production report consumer reads a steer file; Run C/A/B bookkeeping counts `steer` events rather than artifacts.

Do not retain `steer-<attempt>.md` as an accountability mechanism without first amending the reports under blueprint §8, because that would intentionally change the approved artifact model.

## Risks to validate

- Multi-line steering must use tmux buffer/paste rather than `send_line`.
- Full correction text in `events.jsonl` may contain sensitive repository context, but this is less exposure than the current controller-original plus `.pm` mirror duplication.
- Assessment rendering needs readable multiline indentation.
- Fake-harness coverage should test direct delivery, hard-stop refusal, and multiline preservation; static assessment did not execute cross-harness interaction.

## Next action

Use this report as the frozen brief for a new implementation session. After implementation, run a fresh §6.6 review before clearing the owner gate for Runs A/B.
