# AI Orchestrator

A skill for AI coding assistants that turns the current assistant into an **orchestrator** — selectively routing coding and analysis work to external AI CLI tools while retaining ownership of planning, authorization, quality, final synthesis, and final delivery.

## Purpose

The orchestrator delegates selectively when a worker will improve quality, speed, independence, or context management. It keeps work local when the slice is small, prompt construction would cost more than the task, delegation would weaken correctness, or the orchestrator needs tight control of the acceptance boundary.

Workers produce inputs, evidence, drafts, and implementation. The orchestrator remains the finisher and must retain the final user-facing deliverable, authorization decisions, accept-or-reject decisions, and correctness-critical judgment.

This skill is standalone. It can run by itself with only the files in this repository. When installed alongside the other [`ai-engineering-skills`](https://github.com/darrencroton/ai-engineering-skills) skills, it can also coordinate companion skills through the local skill map in [`SKILL.md`](SKILL.md).

## Supported Tools

Supported worker harnesses are defined by the model table in [`SKILL.md`](SKILL.md) and the files in [`references/`](references/). Avoid duplicating that list here; harness support is expected to change as tools are added, removed, or renamed.

## Structure

```
SKILL.md                  # Main skill definition, roles, workflow, model table
ai-reminder               # tmux reminder helper for long-running assistant sessions
scripts/
  worker_contract.py      # semantic policy/request validation and harness command composition
  worker_jobs.py          # validated worker launch/status/activity/cancel/extract helper
references/
  worker-contract.md       # semantic policy/request schema and correction flow
  <harness>.md            # Harness-specific CLI references and commands
  templates.md            # Semantic worker-request templates by task type
```

## Usage

This skill may be loaded natively by an AI coding assistant or embedded by a supervising workflow such as Master Controller. Once loaded, the assistant acts as orchestrator and uses the semantic launcher, templates, and model references to delegate work.

Operating conventions:
- Start with a short execution checklist and keep it updated through the run
- Decide whether delegation is worth the overhead; do not delegate by default
- Name required skills explicitly in the checklist and in each worker prompt, or write `none`
- Use self-contained worker prompts with absolute paths when practical
- Include the frozen contract for implementation work: intended slice, allowed files/functions, expected tests, explicit non-goals, risky surfaces, and validation plan
- For analysis tasks, ask workers to return `SECTION:` markers plus `path:line` evidence
- Write semantic worker policy/request JSON and use `scripts/worker_jobs.py launch`; never construct a worker harness command directly. The launcher validates intent, embeds complete required-skill bundles, composes tested flags, and forces the worker process into the policy repository. Artifacts are written to `.ai-orchestrator/runs/` in the project by default (override with `AI_ORCHESTRATOR_ARTIFACT_ROOT`)
- Read `references/worker-contract.md` for schemas, validation behavior, self-correction feedback, and the launch command
- Use `--run-dir current` to reference the latest run without knowing the timestamped path
- Use `worker_jobs.py activity` as the worker health check; for session-backed tools it reads lightweight session signals, otherwise it uses helper-managed file activity
- Use `worker_jobs.py cancel` to stop workers cleanly and preserve final status
- Use `worker_jobs.py extract` to read each worker's clean final output rather than raw wrapper output; inspect raw stdout or stderr only for failures, malformed extraction, or debugging
- Use `worker_jobs.py extract --json` when you need the extracted text plus its source artifact for debugging
- Use worker labels in lowercase kebab-case: `<nn>-<tool>-<subtask-slug>[-rN]` so files sort cleanly within each run directory
- While workers run, stay in the orchestrator role: monitor status, manage the checklist, and prepare synthesis or follow-up review prompts rather than duplicating the delegated investigation
- Run or request authorization drift audit before quality review when a frozen implementation contract exists

## Explicit Skill Coordination

The orchestrator does not assume workers will infer skills from context. Every worker prompt includes `REQUIRED SKILLS`.

The launcher embeds a required skill and its transitively linked Markdown resources before the process starts. Missing or incomplete required skills fail closed with field-specific feedback; the orchestrator corrects the request or installation and retries.

Common companion skills are listed in the local skill map in [`SKILL.md`](SKILL.md). That map is the source of truth for how orchestration coordinates with other skills.

Companion skills are optional only when the request does not name them. Once listed in `required_skills`, their complete instruction bundle is mandatory for launch.

Trigger conditions:
- The user wants to delegate a task to an external AI agent
- The user mentions a supported external harness explicitly
- The user asks to "use another model"
- The user wants to spread work across multiple models

## Optional Helper

`ai-reminder` is a small companion script for long-running terminal assistant sessions. The skill itself works without it, but on long coding tasks an orchestrator can drift and stop delegating as consistently as the workflow intends. Running `ai-reminder` alongside the session provides a periodic nudge back toward the current task, plan, and delegation discipline.

NOTE: The orchestrator must be running inside a tmux pane for `ai-reminder` to work.

Typical usage:
- `ai-reminder start --tool <harness>`
- `ai-reminder start --tool <harness> --interval 120`

Ensure the script is executable before first use: `chmod +x ai-reminder`.

If you use it regularly, add a shell alias so it can be launched from whatever project you are currently working in. Run `ai-reminder --help` for the full command set and option details.

## Roles

| Role | Purpose | Typical tasks | Hard limits |
|---|---|---|---|
| **Orchestrator** | Human-facing owner and finisher | Planning, delegation, context packaging, verification, testing, final synthesis, final answer/report/recommendation | Only the assistant directly handling the user; must retain the final user-facing deliverable, the acceptance decision, and correctness-critical judgment |
| **Senior worker** | Deep technical work | Multi-file edits, refactors, complex logic, plan review, implementation drafts, evidence gathering | No re-delegation; outputs are inputs or drafts for orchestrator review, not the final deliverable |
| **Junior worker** | Tactical work | Surgical edits, approved git ops, low-stakes research, codebase mapping, support-text drafts | Escalate when scope or importance grows; outputs are inputs or drafts for orchestrator review, not the final deliverable |

## Adding (Removing) a Model

1. Add a new row to the model table in `SKILL.md` (or remove the relevant row)
2. Add `references/<model>.md` following the structure of the existing model files (or remove the relevant file)
3. Update `scripts/worker_jobs.py` if the model needs custom activity, extraction, or session matching behavior
4. Update `README.md` and `AGENTS.md` if the supported structure or maintenance expectations changed
5. Only update `references/templates.md` if the new model requires a new role, prompt shape, or output-extraction pattern
