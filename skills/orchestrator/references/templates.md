# Reviewer Request Templates

Reviewer requests use schema v2 and are intrinsically read-only. Copy `slice_id`, `plan_sha256`, tool, model, and effort from policy. Do not include `role`, `access`, write authorization, or external-operation approval fields.

Use the smallest file list that covers the question. Every file must already exist. Require `path:line` evidence for material claims and an explicit blocker when required coverage is unavailable.

## Investigation or plan verification

```json
{
  "schema_version": 2,
  "label": "01-<tool>-<subtask>",
  "slice_id": "<copy from policy>",
  "plan_sha256": "<copy from policy>",
  "tool": "<copy one required tool from policy>",
  "model": "<copy from policy>",
  "effort": "<copy from policy>",
  "task": "<specific read-only question>",
  "context": "<minimal context and required coverage>",
  "required_skills": [],
  "files": ["<repo-relative existing path>"],
  "constraints": [
    "Cite path:line evidence for every material claim.",
    "Report unchecked required coverage instead of guessing."
  ],
  "expected_output": "Return SECTION: FINDINGS, SECTION: EVIDENCE, SECTION: RISKS, and SECTION: OPEN_QUESTIONS; use - none for empty sections."
}
```

## Drift audit

Use a separate request whose `required_skills` is exactly `["drift-audit"]`. Provide the frozen contract, implementation diff/evidence paths, and the exact surfaces the audit must compare.

## Code review

Launch only after drift audit passes. Use a separate request whose `required_skills` is exactly `["code-review"]`. Provide the validated diff, relevant code/tests, and any accepted risk context.

## Retry

When a launch rejects, read `<label>-request-feedback.md`, correct only the named fields, and retry. A distinct follow-up uses an `-rN` label. Never resume or bypass through a raw harness command.
