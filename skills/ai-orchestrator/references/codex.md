# Codex CLI Reference

## Roles It Can Fill

- **Orchestrator**: Yes
- **Senior worker**: Yes
- **Junior worker**: Not preferred

These are defaults for a normally-configured Codex CLI session, not a fixed guarantee — role fit still depends on the configured model (see Config Discovery). Downgrade the default if the configured model or session evidence doesn't support it.

## Best Used For

- Complex edits and refactors
- Long-running coding tasks
- Plan review and deep debugging

## Avoid Using It For

- Low-value tactical chores when a junior worker is available
- Launching Codex CLI workers from inside a Codex CLI orchestrator session

## Config Discovery

Read `~/.codex/config.toml` for the user's default model (`model` key). Use that model as a starting point unless the user specifies otherwise. Prefer `model_reasoning_effort="high"` for Codex worker tasks, and reserve `xhigh` for especially complex review or synthesis. Prefer omitting `-m` entirely when the configured default is acceptable. Never hardcode model names.

## Deterministic Launch Profile

Write policy/request JSON as documented in [worker-contract.md](worker-contract.md), then use `worker_jobs.py launch`. The launcher owns `codex exec`, model/reasoning flags, sandbox selection, `--skip-git-repo-check`, and working-directory flags; orchestrators must not compose these flags.

## Helper Use

Use [../scripts/worker_jobs.py](../scripts/worker_jobs.py) for per-run directories, status tracking, and extraction. Let it own stdout/stderr capture, and omit shell redirections from the worker command. Worker labels must use `<nn>-<tool>-<subtask-slug>[-rN]`, for example `01-codex-plan-scan`.

Check health with:

```bash
python3 <skill-dir>/scripts/worker_jobs.py activity --run-dir "$run_dir" --label <label>
```

If `healthy=yes`, keep waiting on cadence. Use `cancel` to stop a worker cleanly:

```bash
python3 <skill-dir>/scripts/worker_jobs.py cancel --run-dir "$run_dir" --label <label>
```

Use `worker_jobs.py extract` when you want the clean final answer. Use `worker_jobs.py extract --json` when you need the extracted text plus its source artifact. The helper first reads stdout when it contains the clean answer and falls back to the matched Codex session when needed.

## Notes

- Do not launch Codex CLI as a worker from inside a Codex CLI orchestrator session; choose another worker model or keep that part local.
- For senior multi-file edit or review tasks, wait for the role-appropriate window, then run `worker_jobs.py activity`. An advancing session timestamp, recent assistant activity, or `healthy=yes` means keep waiting.
- If extraction is still empty or malformed after completion, inspect the matching stderr file, retry once with a tighter prompt if appropriate, then fall back.
- While workers run, keep the orchestrator on orchestration work only; do not duplicate the delegated investigation locally.

## Key Flags

| Flag | Values | Notes |
|---|---|---|
| `-m / --model` | any string | From config or user request; omit when the default is acceptable |
| `-c model_reasoning_effort="VALUE"` | string | Prefer `high`; use `xhigh` only for especially complex work or explicit user preference |
| `-s / --sandbox` | `read-only`, `workspace-write`, `danger-full-access` | See Permission Guidance |
| `--full-auto` | — | Alias for `-a on-request --sandbox workspace-write` |
| `-C / --cd` | path | Set working directory |
| `--add-dir` | path | Add additional writable directory |
| `--search` | — | Enable live web search |
| `-o / --output-last-message` | path | Optional Codex flag for standalone use; normally leave unset in tracked worker commands |
| `--json` | — | JSONL event stream; leave unset for normal worker runs |

## Permission Guidance

- **read-only**: analysis, review, plan review
- **workspace-write** / `--full-auto`: any task that modifies files
- **danger-full-access**: only if the user explicitly requests unrestricted execution

Reasoning guidance:

- Default to `high` for Codex worker tasks
- Escalate to `xhigh` only for especially complex review, ambiguity, or synthesis

Worker continuation is not a separate raw-command path. Write a new semantic request with an `-rN` label so policy validation and evidence remain complete.
