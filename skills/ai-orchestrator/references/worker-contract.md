# Deterministic Worker Contract

The orchestrator chooses worker intent. It does not construct harness commands. `scripts/worker_jobs.py launch` validates a semantic JSON request against an authoritative policy, embeds the worker-mode instructions and complete required-skill Markdown bundles, composes the selected harness command from a tested profile, forces the child process into the policy repository, and records the resolved launch evidence.

Inspect machine-readable role/access capabilities with `python3 scripts/worker_jobs.py profiles`. A request outside a profile's tested capabilities is rejected before any process starts.

## Policy

Master Controller writes `worker-policy.json` for an MC slice. A standalone ai-orchestrator may write an equivalent policy from the user's authorization and frozen contract. The policy is the authority for run/slice identity, the frozen plan digest, repository, worker artifact root, required tools, model, effort, permitted roles and access modes, and authorized files. When the plan explicitly requires a read-only worker, MC restricts `allowed_access` to `read-only`. Under MC, every tool in `required_tools` must produce its own validated successful run before the slice can pass.

```json
{
  "schema_version": 1,
  "run_id": "20260710T045454Z",
  "slice_id": "Slice 1",
  "plan_sha256": "<exact frozen plan digest>",
  "repo_path": "/absolute/path/to/repo",
  "worker_artifact_root": "/absolute/path/to/slice/worker-runs",
  "required_tools": ["opencode"],
  "required_model": "macstudio/qwen/qwen3.6-35b-a3b-q8",
  "required_effort": "default",
  "allowed_access": ["read-only", "workspace-write"],
  "allowed_roles": ["junior-worker", "senior-worker"],
  "authorized_files": ["pi_calculator.py"]
}
```

## Request

The orchestrator writes one semantic request per worker. Copy `slice_id` and `plan_sha256` exactly from the current policy. Use `read-only` for analysis, review, validation, or planning. Use `workspace-write` only for a bounded edit authorized by the frozen contract.

```json
{
  "schema_version": 1,
  "label": "01-opencode-format-check",
  "slice_id": "Slice 1",
  "plan_sha256": "<exact value copied from worker-policy.json>",
  "tool": "opencode",
  "model": "macstudio/qwen/qwen3.6-35b-a3b-q8",
  "effort": "default",
  "role": "junior-worker",
  "access": "read-only",
  "task": "Run the configured validation and check the output contract.",
  "context": "The slice extracts a constant without changing output.",
  "required_skills": [],
  "files": ["pi_calculator.py"],
  "constraints": ["Do not edit files.", "Report the actual output."],
  "expected_output": "Start with RESULT: pass or RESULT: blocked, followed by the actual output."
}
```

## Launch

```bash
run_dir="$(python3 scripts/worker_jobs.py init --prefix workers)"
python3 scripts/worker_jobs.py launch \
  --run-dir "$run_dir" \
  --policy /absolute/path/to/worker-policy.json \
  --request /absolute/path/to/worker-request.json
```

Do not bypass a rejected request by invoking `claude`, `codex`, `copilot`, or `opencode` directly. Read `<label>-request-feedback.md`, correct only the named fields, and launch again. Feedback is deliberately specific so even a weak orchestrator can self-correct without redoing the slice.

Successful launches preserve request, policy, rendered prompt, resolved command, normalized contract, enforced working directory, process status, stdout, and stderr in the worker run directory. A named required skill or linked Markdown resource that cannot be embedded rejects the launch before process creation. Under MC, final acceptance requires this validated launch evidence, an exact match to MC's stored policy snapshot, and successful completion for every configured worker tool.
