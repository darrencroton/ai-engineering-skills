# Claude Code Reference

## Roles It Can Fill

- **Orchestrator**: Yes
- **Senior worker**: Yes
- **Junior worker**: Not preferred

These are defaults for a normally-configured Claude Code session, not a fixed guarantee — role fit still depends on the configured model (see Config Discovery). Downgrade the default if the configured model or session evidence doesn't support it.

## Best Used For

- Complex edits and refactors
- Long-running coding tasks
- Plan review and deep debugging

## Avoid Using It For

- Low-value tactical chores when a junior worker is available
- Launching Claude Code workers from inside a Claude Code orchestrator session

## Config Discovery

Read `~/.claude/settings.json` for relevant user defaults if present. If no model is configured there, omit `--model` and let Claude Code use its default. Use `--effort <level>` when the user or supervising workflow specifies an effort level. Never hardcode model names.

## Deterministic Launch Profile

Write policy/request JSON as documented in [worker-contract.md](worker-contract.md), then use `worker_jobs.py launch`. The launcher owns `claude -p`, model/effort flags, `--permission-mode plan|acceptEdits`, text output, and directory scope; orchestrators must not compose these flags.

## Helper Use

Use [../scripts/worker_jobs.py](../scripts/worker_jobs.py) for per-run directories, status tracking, and extraction. Let it own stdout/stderr capture and omit extra shell redirections from the worker command. Worker labels must use `<nn>-<tool>-<subtask-slug>[-rN]`, for example `01-claude-review-plan`.

Check health with:

```bash
python3 <skill-dir>/scripts/worker_jobs.py activity --run-dir "$run_dir" --label <label>
```

If `healthy=yes`, keep waiting on cadence. Use `cancel` to stop a worker cleanly:

```bash
python3 <skill-dir>/scripts/worker_jobs.py cancel --run-dir "$run_dir" --label <label>
```

Use `worker_jobs.py extract` when you want the clean final answer. Use `worker_jobs.py extract --json` when you need the extracted text plus its source artifact. If Claude exits `0` with empty stdout, extraction falls back to the matched Claude session automatically.

## Notes

- Do not launch Claude Code as a worker from inside a Claude Code orchestrator session; nested Claude sessions are blocked.
- For senior multi-file edit or review tasks, wait for the role-appropriate window, then run `worker_jobs.py activity`. An advancing session timestamp, recent assistant activity, or `healthy=yes` means keep waiting.
- If extraction is still empty or malformed after completion, inspect the matching stderr file, retry once with a tighter prompt if appropriate, then fall back.
- While workers run, keep the orchestrator on orchestration work only; do not duplicate the delegated investigation locally.

## Key Flags

| Flag | Notes |
|---|---|
| `-p / --print` | Non-interactive prompt string |
| `--model` | Any valid model string; omit to use the CLI default |
| `--effort` | Reasoning effort level when explicitly requested by the user or supervising workflow |
| `--permission-mode` | Use `acceptEdits` for edit tasks, `plan` for read-only review |
| `--output-format` | `text`, `json`, `stream-json` |
| `--add-dir` | Additional directory to permit tool access to |
| `--continue` | Resume the most recent session in the current directory |
| `--resume` | Resume by session ID or picker |

## Permission Guidance

- **Edit tasks**: `--permission-mode acceptEdits`
- **Read-only review**: `--permission-mode plan`
- **Unrestricted execution**: only if the user explicitly requests it

Worker continuation is not a separate raw-command path. Write a new semantic request with an `-rN` label so policy validation and evidence remain complete.
