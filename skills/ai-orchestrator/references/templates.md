# Worker Request Templates

Use these shapes to write `worker-request.json`. They describe intent; they are never pasted into a harness command. The deterministic launcher validates them against policy, renders worker mode, embeds complete required-skill bundles, composes tool flags, and enforces the repository working directory.

Copy `slice_id`, `plan_sha256`, tool, model, and effort from the current policy. Use the tightest file list that covers the task. Choose `read-only` for investigation, plan review, drift audit, code review, or validation — read-only permits running commands that do not modify the workspace (such as the validation the task names) but forbids creating or editing files. Choose `workspace-write` only for a bounded authorized edit. Use an empty `required_skills` array when no skill is needed.

For information tasks, put literal `SECTION:` markers and `path:line` evidence requirements in `expected_output`. For confirmation tasks, require a literal `RESULT:` line. Missing required skills or linked Markdown resources reject the launch; fix the request or installation and retry.

## Read-Only Investigation or Review

```json
{
  "schema_version": 1,
  "label": "01-<tool>-<subtask>",
  "slice_id": "<copy from policy>",
  "plan_sha256": "<copy from policy>",
  "tool": "<copy one required tool from policy>",
  "model": "<copy from policy>",
  "effort": "<copy from policy>",
  "role": "senior-worker",
  "access": "read-only",
  "task": "<specific question or audit>",
  "context": "<minimal task-specific context and required coverage>",
  "required_skills": ["<exact skill name when required>"],
  "files": ["<repo-relative input path>"],
  "constraints": [
    "Do not edit files.",
    "Cite path:line evidence for every material claim.",
    "Report unchecked required coverage instead of guessing."
  ],
  "expected_output": "Return only SECTION: FINDINGS, SECTION: EVIDENCE, SECTION: RISKS, and SECTION: OPEN_QUESTIONS; use - none for empty sections."
}
```

## Bounded Edit

```json
{
  "schema_version": 1,
  "label": "01-<tool>-<subtask>",
  "slice_id": "<copy from policy>",
  "plan_sha256": "<copy from policy>",
  "tool": "<copy one required tool from policy>",
  "model": "<copy from policy>",
  "effort": "<copy from policy>",
  "role": "<junior-worker for a surgical edit; senior-worker for complex bounded work>",
  "access": "workspace-write",
  "task": "<one imperative, bounded change>",
  "context": "<frozen contract, exact target, current state, validation plan, and relevant approval state>",
  "required_skills": ["scoped-implementation"],
  "files": ["<repo-relative authorized path>"],
  "constraints": [
    "Stay inside the frozen contract.",
    "Do not touch other files or refactor surrounding code.",
    "Stop and report blocked if the task requires expanded authorization."
  ],
  "expected_output": "Return RESULT: followed by one or two sentences describing the change and validation result, or RESULT: blocked - <reason>."
}
```

## Tactical Operation

Use a `junior-worker` and keep `task`, `files`, and `constraints` narrowly scoped. State-changing git, GitHub, or external operations still require explicit user authorization in the request context. Workers never commit under Master Controller; the orchestrator owns the commit gate.

## Retry

When launch rejects a request, read `<label>-request-feedback.md`, correct only the named fields, and retry. If a completed worker needs a distinct follow-up, write a new request with the same contract and an `-rN` label. Never resume or bypass through a raw harness command.
