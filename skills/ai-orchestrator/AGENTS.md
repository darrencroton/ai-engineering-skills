# AI Orchestrator Repo Guide

## Purpose

This repo defines the `ai-orchestrator` skill. It teaches an AI coding agent how to delegate work to external AI CLIs while keeping one orchestrator responsible for planning, monitoring, verification, and final synthesis.

## File Roles

- `README.md`: human-facing overview and short maintenance notes
- `SKILL.md`: source of truth for generic orchestration workflow, role selection, monitoring cadence, and helper usage
- `references/worker-contract.md`: semantic policy/request schema, launch flow, and rejection behavior
- `references/templates.md`: semantic request shapes only
- `references/claude.md`, `references/codex.md`, `references/copilot.md`, `references/opencode.md`: model-specific CLI references; keep the same structure across senior-worker model files and only change the model-specific details
- `scripts/worker_contract.py`: validates semantic policy/request artifacts, embeds complete required-skill bundles, and composes harness commands
- `scripts/worker_jobs.py`: validated contract launcher plus tracked-process lifecycle and the `status`, `activity`, `cancel`, and `extract` CLI
- `scripts/worker_sessions.py`: Claude Code and Codex CLI session discovery, activity signals, and transcript extraction fallbacks
- `ai-reminder`: separate tmux/session reminder helper for long-running Claude/Codex sessions

Do not mix these purposes. Keep model-specific CLI flags and monitoring details out of `SKILL.md`. Keep prompt-shape guidance out of the model reference files.

## Working Rules

- Use `scripts/worker_jobs.py launch` with policy/request JSON for worker launches and artifact tracking; raw harness commands are not a supported launch path
- Use `worker_jobs.py activity` as the health check, `cancel` to stop workers cleanly, and `extract` to read the clean final answer
- Session-backed tools must be monitored indirectly from lightweight signals; do not require the orchestrator to read full session logs to decide whether a worker is healthy
- Worker labels use `<nn>-<tool>-<subtask-slug>[-rN]`
- If an edit prompt follows a planning prompt, carry exact targets into the edit prompt: `path:line`, function names, and snippets where useful
- Keep worker outputs compact and scanner-friendly with `SECTION:` and `RESULT:` conventions from `references/templates.md`

## When Changing Model Support

- Update the model table in `SKILL.md`
- Add, remove, or revise `references/<model>.md`
- Update `scripts/worker_contract.py` for launch capabilities/flags, `scripts/worker_sessions.py` for session matching and transcript interpretation, and `scripts/worker_jobs.py` for tracked-process lifecycle or CLI behavior
- Update `README.md` and this file if structure or maintenance expectations changed
- Update `references/templates.md` only if prompt shape or output contract changes

## Verification

- Run `python3 -m py_compile scripts/worker_contract.py scripts/worker_sessions.py scripts/worker_jobs.py` after helper changes
- Run `python3 -m unittest discover -s tests` for contract and launcher changes
- Replay a relevant artifact or run a small smoke test when changing `activity`, `cancel`, or `extract`
