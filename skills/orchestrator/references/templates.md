# Delegate Request Templates

Delegate requests use schema v3. Copy `slice_id`, `plan_sha256`, tool, model, and effort from policy. Set `access` to one of policy's `required_access` values. Do not include `role`, an unauthorized `access` value, or any external-operation approval field.

Use the smallest file list that covers the question. Every file in `files` must already exist. Require `path:line` evidence for material claims and an explicit blocker when required coverage is unavailable.

## Investigation or plan verification (`access: read-only`)

```json
{
  "schema_version": 3,
  "label": "01-<tool>-<subtask>",
  "slice_id": "<copy from policy>",
  "plan_sha256": "<copy from policy>",
  "tool": "<copy one required tool from policy>",
  "model": "<copy from policy>",
  "effort": "<copy from policy>",
  "access": "read-only",
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

## Drift audit (`access: read-only`)

Use a separate request whose `required_skills` is exactly `["drift-audit"]`. Provide the frozen contract, implementation diff/evidence paths, and the exact surfaces the audit must compare.

## Code review (`access: read-only`)

Launch only after drift audit passes. Use a separate request whose `required_skills` is exactly `["code-review"]`. Provide the validated diff, relevant code/tests, and any accepted risk context.

## Bounded implementation (`access: read-write`)

Only valid against a policy whose `required_access` includes `read-write`. Requires `authorized_surface` and `non_goals`, both non-empty; both are rejected on a `read-only` request (by key presence, not by whether the list happens to be empty).

```json
{
  "schema_version": 3,
  "label": "02-<tool>-<subtask>",
  "slice_id": "<copy from policy>",
  "plan_sha256": "<copy from policy>",
  "tool": "<copy one required tool from policy>",
  "model": "<copy from policy>",
  "effort": "<copy from policy>",
  "access": "read-write",
  "task": "<specific, bounded implementation task>",
  "context": "<the frozen slice or contract this task comes from>",
  "required_skills": [],
  "files": ["<repo-relative existing path a delegate should read for context>"],
  "authorized_surface": ["<file: specific function/behavior it may add or change>"],
  "non_goals": ["<explicitly excluded file, function, or behavior>"],
  "constraints": [
    "Run the existing test suite before reporting done.",
    "Report every file you touched, not just the ones you intended to."
  ],
  "expected_output": "List every changed file with a one-line summary, and the test command you ran with its result."
}
```

After extraction, review the delegate's diff yourself before keeping it, then run `drift-audit` against it exactly as you would for your own implementation.

## Retry

When a launch rejects, read `<label>-request-feedback.md`, correct only the named fields, and retry. A distinct follow-up uses an `-rN` label. Never resume or bypass through a raw harness command.
