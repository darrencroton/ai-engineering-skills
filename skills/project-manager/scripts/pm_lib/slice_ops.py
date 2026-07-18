"""Command orchestration for the slice lifecycle (target-design §3/§12).

This module wires the pieces other `pm_lib` modules already provide —
`state`, `plan`, `git_ops`, `sessions`, `profiles`, `prompts` — into the
per-command sequences described in target-design and the Stage 3 brief. It
decides nothing semantic: no accept/reject exists here (that lands in
Stage 4, through `finalize --accept/--steer/--stop`). Every function either
mutates state through the token-authenticated `state` module, drives tmux
through `sessions`, or reads git/filesystem facts through `git_ops` — it
never itself renders prose or judges evidence; `floor.py` computes the
facts, and only a human or a later-stage PM agent turns them into a
decision.
"""

from __future__ import annotations

import json
import re
import shlex
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import IntegrityError, PmError
from . import git_ops
from . import plan as plan_mod
from . import profiles
from . import prompts
from . import sessions
from . import state as state_mod
from .floor import FloorReport, evaluate_floor

_SLICE_ID_RE = re.compile(r"^Slice\s+(?P<number>\d+)$")

# Artifact rotation / observe polling.
_OBSERVE_POLL_SECONDS = 2.0
_OBSERVE_TAIL_LINES = 40


# --- Path helpers ------------------------------------------------------------


def pm_dir(repo: Path) -> Path:
    return repo / ".pm"


def runs_root(repo: Path) -> Path:
    return pm_dir(repo) / "runs"


def run_artifact_dir(repo: Path, run_id: str) -> Path:
    return runs_root(repo) / run_id


def notes_path(repo: Path, run_id: str) -> Path:
    return run_artifact_dir(repo, run_id) / "notes.md"


def slice_number(slice_id: str) -> int:
    match = _SLICE_ID_RE.match(slice_id)
    if not match:
        raise PmError(f"slice id {slice_id!r} is not in the expected 'Slice <N>' shape")
    return int(match.group("number"))


def slice_artifact_dir(repo: Path, run_id: str, slice_id: str) -> Path:
    return run_artifact_dir(repo, run_id) / "slices" / f"slice-{slice_number(slice_id):03d}"


def write_pm_gitignore(repo: Path) -> None:
    """A self-ignoring `.pm/.gitignore` (a bare `*`) so the artifact tree never
    needs individual entries in the repository's own `.gitignore`."""
    directory = pm_dir(repo)
    directory.mkdir(parents=True, exist_ok=True)
    gitignore = directory / ".gitignore"
    gitignore.write_text("*\n", encoding="utf-8")


# --- Shared state access ------------------------------------------------------


def repo_from_cwd(cwd: Path) -> Path:
    return git_ops.resolve_repo(cwd)


def load_writable_state(run_dir: Path, token: str) -> dict[str, Any]:
    """Load + MAC-verify state for a mutating command.

    An integrity failure is terminal by construction: the unauthenticated
    run.json is deliberately NOT rewritten or re-signed — re-signing would
    turn attacker-controlled bytes (say, a Developer marking its own slice
    accepted) into MAC-valid state. Left unsigned, every future mutating
    command keeps failing closed on the same IntegrityError, the tampered
    file survives as evidence, and recovery is the operator's decision
    (start a new run). Only the append-only event log records the
    detection, since events carry no authority.
    """
    try:
        return state_mod.load_state(run_dir, token)
    except IntegrityError as exc:
        try:
            state_mod.append_event(run_dir, "stop", note=f"state integrity check failed: {exc}")
        except PmError:
            pass
        raise


def _slice_entry(state: dict[str, Any], slice_id: str) -> dict[str, Any] | None:
    for entry in state.get("slices", []):
        if isinstance(entry, dict) and entry.get("id") == slice_id:
            return entry
    return None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_id_session_prefix(run_id: str) -> str:
    return f"pm-{run_id}"


# --- init ---------------------------------------------------------------------


@dataclass
class InitResult:
    run_id: str
    run_dir: Path
    token: str
    state: dict[str, Any]
    slices: list[plan_mod.PlanSlice]
    branch: str


def init_run(
    repo: Path,
    plan_path: Path,
    *,
    harness: str,
    model: str | None,
    effort: str | None,
    branch: str | None,
    create_branch: str | None,
    attest: str | None,
    max_attempts: int | None,
    reviewer_tools: str | None,
    reviewer_model: str | None,
    reviewer_effort: str | None,
    harness_command: str | None,
) -> InitResult:
    """Preflight, branch setup, and state/artifact creation for `init`.

    Callers are expected to have already run `plan.plan_check_report` and
    stopped on errors (this function assumes the plan is clean); it does
    not re-check the plan.
    """
    if not _tmux_present():
        raise PmError("tmux is required to run PM; install it before running init")

    if harness_command is None and harness not in profiles.SUPPORTED_HARNESSES:
        supported = ", ".join(profiles.SUPPORTED_HARNESSES)
        raise PmError(
            f"no PM harness profile is defined for {harness!r} and no --harness-command override was "
            f"given; supported harnesses: {supported}"
        )

    if harness_command:
        candidate_executable = shlex.split(harness_command)[0] if harness_command.strip() else ""
    else:
        candidate_executable = profiles.HARNESS_PROFILES[harness]["base_command"][0]
    if not candidate_executable or not _executable_exists(candidate_executable):
        raise PmError(f"harness executable not found on PATH: {candidate_executable!r}")

    resolved_branch = _resolve_init_branch(repo, branch=branch, create_branch=create_branch)
    # Required in every case, including after a branch switch and on the
    # "use the current branch" path, which has no earlier clean check.
    git_ops.require_clean_worktree(repo)

    slices = plan_mod.parse_plan(plan_path)
    known_ids = {plan_slice.slice_id for plan_slice in slices}
    attested_ids: set[str] = set()
    if attest:
        attested_ids = {piece.strip() for piece in attest.split(",") if piece.strip()}
        unknown = attested_ids - known_ids
        if unknown:
            raise PmError(f"--attest names unknown slice id(s): {', '.join(sorted(unknown))}")

    entries = [
        {
            "id": plan_slice.slice_id,
            "title": plan_slice.title,
            "status": "attested" if plan_slice.slice_id in attested_ids else None,
            "risk": plan_slice.plan_risk,
            "plan_risk": plan_slice.plan_risk,
            "commit": None,
            "attempts": 0,
        }
        for plan_slice in slices
    ]

    harness_block = {"name": harness, "model": model, "effort": effort, "command_override": harness_command}
    reviewer_block = {
        "tools": list(profiles.parse_reviewer_tools(reviewer_tools)),
        "model": reviewer_model,
        "effort": reviewer_effort,
    }
    policy_block = {"max_attempts": max_attempts if max_attempts is not None else 3, "commit_required": True}

    state, token, run_dir = state_mod.create_run(
        repo,
        plan_path=plan_path,
        plan_sha256=plan_mod.plan_digest(plan_path),
        slice_count=len(slices),
        branch=resolved_branch,
        harness=harness_block,
        reviewer=reviewer_block,
        policy=policy_block,
        slices=entries,
    )

    write_pm_gitignore(repo)
    (run_artifact_dir(repo, state["run_id"]) / "slices").mkdir(parents=True, exist_ok=True)
    state_mod.append_event(
        run_dir, "init", note=f"harness={harness} branch={resolved_branch} slices={len(slices)}"
    )

    return InitResult(run_id=state["run_id"], run_dir=run_dir, token=token, state=state, slices=slices, branch=resolved_branch)


def _tmux_present() -> bool:
    import shutil

    return shutil.which("tmux") is not None


def _executable_exists(executable: str) -> bool:
    import shutil

    return shutil.which(executable) is not None


def _resolve_init_branch(repo: Path, *, branch: str | None, create_branch: str | None) -> str:
    if create_branch:
        git_ops.require_clean_worktree(repo)
        git_ops.git(repo, "checkout", "-b", create_branch)
        return create_branch
    if branch:
        git_ops.require_clean_worktree(repo)
        returncode, _stdout, _stderr = git_ops.git_result(repo, "rev-parse", "--verify", f"refs/heads/{branch}")
        if returncode != 0:
            raise PmError(f"branch {branch!r} does not exist; create it first or pass --create-branch")
        git_ops.git(repo, "checkout", branch)
        return branch
    current = git_ops.current_branch(repo)
    if current is None:
        raise PmError(
            "current HEAD is detached or the repository is unborn; pass --branch <existing> or "
            "--create-branch <new> so PM has a named branch to operate on"
        )
    return current


# --- status ---------------------------------------------------------------


@dataclass
class StatusResult:
    state: dict[str, Any]
    slices: list[plan_mod.PlanSlice] | None
    plan_error: str | None
    next_slice_id: str | None
    next_slice_eligible: bool | None
    next_slice_reasons: list[str]
    current_session_alive: bool | None


def status(repo: Path, run_dir: Path) -> StatusResult:
    state = state_mod.load_state(run_dir)
    plan_error: str | None = None
    slices: list[plan_mod.PlanSlice] | None = None
    try:
        slices = plan_mod.parse_plan(Path(state["plan"]["path"]))
    except OSError as exc:
        plan_error = str(exc)

    next_slice_id = None
    next_eligible: bool | None = None
    next_reasons: list[str] = []
    if slices is not None:
        approved_ids = frozenset((state.get("approvals") or {}).keys())
        next_plan_slice = plan_mod.next_slice(slices, state)
        if next_plan_slice is not None:
            next_slice_id = next_plan_slice.slice_id
            next_eligible, next_reasons = plan_mod.eligibility(next_plan_slice, approved_ids)

    current = state.get("current_slice")
    current_alive: bool | None = None
    if current and current.get("tmux_session"):
        current_alive = sessions.session_exists(current["tmux_session"])

    return StatusResult(
        state=state,
        slices=slices,
        plan_error=plan_error,
        next_slice_id=next_slice_id,
        next_slice_eligible=next_eligible,
        next_slice_reasons=next_reasons,
        current_session_alive=current_alive,
    )


# --- approve ----------------------------------------------------------------


def approve(repo: Path, run_dir: Path, token: str, *, slice_id: str, reason: str) -> dict[str, Any]:
    state = load_writable_state(run_dir, token)
    slices = plan_mod.parse_plan(Path(state["plan"]["path"]))
    plan_slice = plan_mod.plan_slice_by_id(slices, slice_id)
    if plan_slice is None:
        raise PmError(f"{slice_id} was not found in the plan")
    if plan_slice.approval_needed is not True:
        raise PmError(
            f"{slice_id} is not approval-gated (its Risk Flags 'Approval needed before implementation:' "
            f"line is {plan_slice.approval_needed!r}, not an explicit 'yes'); an unclear or absent flag "
            "is a planning defect that approval cannot clear"
        )
    approvals = dict(state.get("approvals") or {})
    approvals[slice_id] = {"at": _utc_now_iso(), "reason": reason}
    state["approvals"] = approvals
    state_mod.save_state(run_dir, state, token)
    state_mod.append_event(run_dir, "approve", slice_id=slice_id, note=reason)
    return state


# --- start-slice --------------------------------------------------------------


@dataclass
class StartSliceOutcome:
    kind: str  # all_complete | blocked | plan_changed | attempts_exhausted | launched | relaunched
    slice_id: str | None = None
    reasons: list[str] = field(default_factory=list)
    attempt: int | None = None
    session: str | None = None
    reaped: list[str] = field(default_factory=list)
    message: str = ""


def _rotate_prior_attempt(artifact_dir: Path, superseded_attempt: int) -> None:
    names = ("result.json", "pane.txt", "pane-live.txt")
    present = [name for name in names if (artifact_dir / name).exists()]
    if not present:
        return
    destination = artifact_dir / f"attempt-{superseded_attempt}"
    destination.mkdir(parents=True, exist_ok=True)
    for name in present:
        (artifact_dir / name).rename(destination / name)


def start_slice(
    repo: Path,
    run_dir: Path,
    token: str,
    *,
    model: str | None = None,
    effort: str | None = None,
    reviewer_tools: str | None = None,
    harness_command: str | None = None,
) -> StartSliceOutcome:
    state = load_writable_state(run_dir, token)
    run_id = state["run_id"]
    plan_path = Path(state["plan"]["path"])

    try:
        plan_mod.verify_plan_unchanged(state, plan_path)
    except PmError as exc:
        state["status"] = "needs-human"
        state["stop_reason"] = "plan file changed mid-run"
        state_mod.save_state(run_dir, state, token)
        state_mod.append_event(run_dir, "plan-changed", note=str(exc))
        return StartSliceOutcome(kind="plan_changed", message=str(exc))

    slices = plan_mod.parse_plan(plan_path)

    current = state.get("current_slice")
    relaunch = False
    plan_slice: plan_mod.PlanSlice | None = None
    if current and current.get("id"):
        entry = _slice_entry(state, current["id"])
        if entry is not None and entry.get("status") not in ("accepted", "attested"):
            plan_slice = plan_mod.plan_slice_by_id(slices, current["id"])
            relaunch = plan_slice is not None

    if not relaunch:
        plan_slice = plan_mod.next_slice(slices, state)
        if plan_slice is None:
            return StartSliceOutcome(kind="all_complete")

    assert plan_slice is not None
    approved_ids = frozenset((state.get("approvals") or {}).keys())
    eligible, reasons = plan_mod.eligibility(plan_slice, approved_ids)
    if not eligible:
        return StartSliceOutcome(kind="blocked", slice_id=plan_slice.slice_id, reasons=reasons)

    current_branch = git_ops.current_branch(repo)
    if current_branch != state.get("branch"):
        raise PmError(
            f"current branch {current_branch!r} does not match the run's recorded branch "
            f"{state.get('branch')!r}; switch back before starting a slice"
        )
    if not relaunch:
        git_ops.require_clean_worktree(repo)

    entry = _slice_entry(state, plan_slice.slice_id)
    if entry is None:
        raise PmError(f"{plan_slice.slice_id} is not present in the run's slice entries")

    policy = state.get("policy") or {}
    max_attempts = int(policy.get("max_attempts", 3))

    if relaunch:
        attempts = int(entry.get("attempts", 0)) + 1
        if attempts > max_attempts:
            state["status"] = "needs-human"
            state["stop_reason"] = "attempt budget exhausted"
            state_mod.save_state(run_dir, state, token)
            state_mod.append_event(
                run_dir, "stop", slice_id=plan_slice.slice_id, note="attempt budget exhausted"
            )
            return StartSliceOutcome(kind="attempts_exhausted", slice_id=plan_slice.slice_id)
    else:
        attempts = 0

    artifact_dir = slice_artifact_dir(repo, run_id, plan_slice.slice_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    if relaunch:
        _rotate_prior_attempt(artifact_dir, attempts - 1)

    reaped: list[str] = []
    for name in sessions.sessions_with_prefix(_run_id_session_prefix(run_id)):
        sessions.force_stop(name)
        reaped.append(name)

    if relaunch:
        before_head = current.get("before_head") if current else None
    else:
        before_head = git_ops.git_head(repo)
        (artifact_dir / "status-before.txt").write_text(git_ops.git_status_text(repo), encoding="utf-8")

    slice_notes_path = notes_path(repo, run_id)
    result_path = artifact_dir / "result.json"
    prompt_text = prompts.render_developer_prompt(
        plan_slice,
        plan_path=plan_path,
        artifact_dir=artifact_dir,
        notes_path=slice_notes_path,
        result_path=result_path,
    )
    prompt_path = artifact_dir / "prompt.md"
    prompt_path.write_text(prompt_text, encoding="utf-8")

    tmp_dir = artifact_dir / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    env = {
        "PM_SLICE_ARTIFACT_DIR": str(artifact_dir),
        "PM_PLAN_PATH": str(plan_path),
        "PM_SLICE_ID": plan_slice.slice_id,
        "PM_NOTES_PATH": str(slice_notes_path),
        "PM_RESULT_PATH": str(result_path),
        "TMPDIR": str(tmp_dir),
    }

    harness_block = state.get("harness") or {}
    harness_name = harness_block.get("name")
    effective_override = harness_command or harness_block.get("command_override")
    launch_model = model or harness_block.get("model")
    launch_effort = effort or harness_block.get("effort")

    expected_model_display: str | None = None
    if effective_override:
        command = effective_override
    else:
        git_access_dir = None
        session_id = None
        if harness_name == "codex" and bool(policy.get("commit_required", True)):
            git_access_dir = git_ops.worktree_git_dir(repo)
        if harness_name == "claude":
            session_id = str(uuid.uuid4())
        if harness_name == "opencode" and launch_model:
            identity = profiles.query_model_identity(harness_name, launch_model)
            if identity:
                expected_model_display = identity["display_name"]
        command = profiles.compose_command(
            harness_name,
            model=launch_model,
            effort=launch_effort,
            git_access_dir=git_access_dir,
            session_id=session_id,
        )

    session_name = sessions.session_name(run_id, slice_number(plan_slice.slice_id), attempts)
    sessions.start_session(session_name, repo, command, env)
    launch_executable = shlex.split(command)[0] if command.strip() else ""
    sessions.wait_until_ready(session_name, launch_executable, expected_model_display=expected_model_display)
    sessions.send_prompt(session_name, prompt_path)

    now = _utc_now_iso()
    new_current: dict[str, Any] = {
        "id": plan_slice.slice_id,
        "artifact_dir": str(artifact_dir),
        "tmux_session": session_name,
        "before_head": before_head,
        "started_at": (current.get("started_at") if relaunch and current and current.get("started_at") else now),
        "attempts": attempts,
        "risk": entry.get("risk", plan_slice.plan_risk),
        "plan_risk": plan_slice.plan_risk,
        "wake_at": None,
        "reviewer_pids": [],
    }
    launch_overrides = {key: value for key, value in (("model", model), ("effort", effort)) if value}
    if launch_overrides:
        new_current["launch"] = launch_overrides

    state["current_slice"] = new_current
    entry["attempts"] = attempts
    # A successful launch reactivates a run that a human resumed after a
    # stop/needs-human pause; tampered state can never reach here (the MAC
    # check above fails closed before any launch).
    state["status"] = "active"
    state_mod.save_state(run_dir, state, token)
    note = f"attempt {attempts}"
    if reaped:
        note += f"; reaped stale sessions: {', '.join(reaped)}"
    state_mod.append_event(
        run_dir,
        "relaunch" if relaunch else "launch",
        slice_id=plan_slice.slice_id,
        note=note,
        evidence=str(prompt_path),
    )

    return StartSliceOutcome(
        kind="relaunched" if relaunch else "launched",
        slice_id=plan_slice.slice_id,
        attempt=attempts,
        session=session_name,
        reaped=reaped,
    )


# --- observe ------------------------------------------------------------------


@dataclass
class ObserveOutcome:
    has_current_slice: bool
    running: bool = False
    pane_changed: bool = False
    result_present: bool = False
    result_status: str | None = None
    hard_stop: dict[str, Any] = field(default_factory=lambda: {"present": False, "kinds": [], "markers": []})
    tail: str = ""
    slice_id: str | None = None


def observe(repo: Path, run_dir: Path, *, wait: float | None = None) -> ObserveOutcome:
    state = state_mod.load_state(run_dir)
    current = state.get("current_slice")
    if not current or not current.get("tmux_session"):
        return ObserveOutcome(has_current_slice=False)

    session = current["tmux_session"]
    artifact_dir = Path(current["artifact_dir"])
    pane_live_path = artifact_dir / "pane-live.txt"
    previous_capture = pane_live_path.read_text(encoding="utf-8") if pane_live_path.exists() else ""
    result_path = artifact_dir / "result.json"

    initial_running = sessions.session_exists(session)
    result_existed_before = result_path.is_file()

    deadline = time.monotonic() + wait if wait else None
    activity = sessions.detect_activity(session, previous_capture)
    while deadline is not None and time.monotonic() < deadline:
        if activity["active"] or not activity["running"] or result_path.is_file():
            break
        time.sleep(_OBSERVE_POLL_SECONDS)
        activity = sessions.detect_activity(session, previous_capture)

    capture = activity["capture"]
    pane_changed = capture != previous_capture
    if pane_changed:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        pane_live_path.write_text(capture, encoding="utf-8")

    result_present = result_path.is_file()
    result_status: str | None = None
    if result_present:
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                result_status = data.get("status")
        except (OSError, json.JSONDecodeError):
            result_status = None

    hard_stop = sessions.scan_hard_stop(capture)
    tail_lines = capture.splitlines()[-_OBSERVE_TAIL_LINES:]
    tail = "\n".join(tail_lines)

    liveness_changed = activity["running"] != initial_running
    result_newly_appeared = result_present and not result_existed_before
    if pane_changed or liveness_changed or result_newly_appeared:
        state_mod.append_event(
            run_dir,
            "observe",
            slice_id=current.get("id"),
            note=(
                f"pane_changed={pane_changed} liveness_changed={liveness_changed} "
                f"running={activity['running']} result_present={result_present}"
            ),
            evidence=str(pane_live_path) if pane_changed else None,
        )

    return ObserveOutcome(
        has_current_slice=True,
        running=activity["running"],
        pane_changed=pane_changed,
        result_present=result_present,
        result_status=result_status,
        hard_stop=hard_stop,
        tail=tail,
        slice_id=current.get("id"),
    )


# --- send ---------------------------------------------------------------------


def send(repo: Path, run_dir: Path, token: str, *, text: str, reason: str) -> None:
    state = load_writable_state(run_dir, token)
    current = state.get("current_slice")
    session = current.get("tmux_session") if current else None
    if not current or not session or not sessions.session_exists(session):
        raise PmError("no live session — not driving a dead pane")
    sessions.send_line(session, text)
    state_mod.append_event(run_dir, "send", slice_id=current.get("id"), note=reason)


# --- finalize (evidence mode only, this stage) ---------------------------------


@dataclass
class FinalizeOutcome:
    report: FloorReport
    artifact_dir: Path
    pane_path: Path
    status_before_path: Path
    status_after_path: Path
    diff_path: Path
    result_path: Path
    slice_id: str


def finalize(repo: Path, run_dir: Path, token: str) -> FinalizeOutcome:
    state = load_writable_state(run_dir, token)
    current = state.get("current_slice")
    if not current:
        raise PmError("no current slice to finalize")

    slice_id = current["id"]
    artifact_dir = Path(current["artifact_dir"])
    session = current.get("tmux_session")
    pane_text = sessions.pane_text(session) if session and sessions.session_exists(session) else ""

    pane_path = artifact_dir / "pane.txt"
    pane_path.write_text(pane_text, encoding="utf-8")

    status_after_path = artifact_dir / "status-after.txt"
    status_after_path.write_text(git_ops.git_status_text(repo), encoding="utf-8")

    diff_path = artifact_dir / "diff.patch"
    after_head = git_ops.git_head(repo)
    git_ops.write_git_diff(repo, current.get("before_head"), after_head, diff_path)

    slices = plan_mod.parse_plan(Path(state["plan"]["path"]))
    report = evaluate_floor(repo, state, slices, slice_id, artifact_dir=artifact_dir, pane_text=pane_text)

    note = "8/8 passed" if report.passed else "failed: " + ", ".join(
        fact.name for fact in report.facts if not fact.passed
    )
    state_mod.append_event(run_dir, "floor", slice_id=slice_id, note=note, evidence=str(artifact_dir))
    # updated_at bump only — no semantic field changes at this stage.
    state_mod.save_state(run_dir, state, token)

    return FinalizeOutcome(
        report=report,
        artifact_dir=artifact_dir,
        pane_path=pane_path,
        status_before_path=artifact_dir / "status-before.txt",
        status_after_path=status_after_path,
        diff_path=diff_path,
        result_path=artifact_dir / "result.json",
        slice_id=slice_id,
    )


# --- stop -----------------------------------------------------------------


@dataclass
class StopOutcome:
    run_id: str
    killed: list[str]


def stop(
    repo: Path,
    run_dir: Path,
    token: str,
    *,
    reason: str,
    slice_status: str | None = None,
) -> StopOutcome:
    state = load_writable_state(run_dir, token)
    run_id = state["run_id"]
    current = state.get("current_slice")

    if current and current.get("artifact_dir"):
        artifact_dir = Path(current["artifact_dir"])
        session = current.get("tmux_session")
        pane_text = sessions.pane_text(session) if session else ""
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "pane.txt").write_text(pane_text, encoding="utf-8")

    killed: list[str] = []
    for name in sessions.sessions_with_prefix(_run_id_session_prefix(run_id)):
        sessions.force_stop(name)
        killed.append(name)

    if state.get("status") != "complete":
        state["status"] = "stopped"
    state["stop_reason"] = reason
    if slice_status and current and current.get("id"):
        entry = _slice_entry(state, current["id"])
        if entry is not None:
            entry["status"] = slice_status

    state_mod.save_state(run_dir, state, token)
    state_mod.append_event(
        run_dir,
        "stop",
        slice_id=current.get("id") if current else None,
        note=reason,
        evidence=", ".join(killed) if killed else None,
    )
    return StopOutcome(run_id=run_id, killed=killed)


def stop_scavenge_sweep(*, run_id: str | None) -> list[str]:
    """State-independent tmux sweep for `stop --scavenge` when state cannot be
    trusted or read at all. Narrows to the given run id's sessions when one
    is known; otherwise sweeps every PM session regardless of run."""
    prefix = _run_id_session_prefix(run_id) if run_id else "pm-"
    killed: list[str] = []
    for name in sessions.sessions_with_prefix(prefix):
        sessions.force_stop(name)
        killed.append(name)
    return killed
