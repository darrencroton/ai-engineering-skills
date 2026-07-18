"""Command-line parsing and dispatch (target-design §12).

Stage 1 implements `check-plan` only. Every other command is wired into the
parser now (so flag shapes are frozen) but exits 2 with a not-yet-available
message when invoked — later stages replace those stubs one at a time.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import PmError
from . import plan as plan_mod

# Mutating commands accept --token, falling back to PM_RUN_TOKEN in the
# controller's environment. The plumbing is defined now; nothing reads it
# until the commands it guards are implemented.
_TOKEN_ENV_VAR = "PM_RUN_TOKEN"

# Commands not yet implemented, in Stage 1. Each exits 2 with a clear message.
_NOT_YET_AVAILABLE = (
    "init",
    "status",
    "approve",
    "start-slice",
    "observe",
    "send",
    "finalize",
    "review",
    "stop",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pm", description="Mode B Lite project manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_plan = subparsers.add_parser("check-plan", help="Validate a plan file")
    check_plan.add_argument("--plan", required=True)
    check_plan.add_argument("--repo")

    init = subparsers.add_parser("init", help="Set up a new PM run")
    init.add_argument("--repo", required=True)
    init.add_argument("--plan", required=True)
    init.add_argument("--harness", required=True)
    init.add_argument("--model")
    init.add_argument("--effort")
    branch_group = init.add_mutually_exclusive_group()
    branch_group.add_argument("--branch")
    branch_group.add_argument("--create-branch")
    init.add_argument("--attest", help='comma-separated slice ids, e.g. "Slice 1,Slice 2"')
    init.add_argument("--max-attempts", type=int)
    init.add_argument("--reviewer-tools", help="comma-separated tool names")
    init.add_argument("--reviewer-model")
    init.add_argument("--reviewer-effort")
    init.add_argument("--harness-command")

    status = subparsers.add_parser("status", help="Show run status")
    status.add_argument("--report", action="store_true")
    status.add_argument("--run")

    approve = subparsers.add_parser("approve", help="Record a human approval for a gated slice")
    approve.add_argument("--slice", required=True)
    approve.add_argument("--reason", required=True)
    approve.add_argument("--run")
    approve.add_argument("--token")

    start_slice = subparsers.add_parser("start-slice", help="Run the next eligible slice")
    start_slice.add_argument("--model")
    start_slice.add_argument("--effort")
    start_slice.add_argument("--reviewer-tools")
    start_slice.add_argument("--harness-command")
    start_slice.add_argument("--run")
    start_slice.add_argument("--token")

    observe = subparsers.add_parser("observe", help="Show evidence of the live session's progress")
    observe.add_argument("--wait", type=float)
    observe.add_argument("--run")

    send = subparsers.add_parser("send", help="Steer the live session")
    send.add_argument("--text", required=True)
    send.add_argument("--reason", required=True)
    send.add_argument("--run")
    send.add_argument("--token")

    finalize = subparsers.add_parser("finalize", help="Run the floor and collect assessment evidence")
    finalize_group = finalize.add_mutually_exclusive_group()
    finalize_group.add_argument("--accept")
    finalize_group.add_argument("--steer")
    finalize_group.add_argument("--stop")
    finalize.add_argument("--run")
    finalize.add_argument("--token")

    review = subparsers.add_parser("review", help="Commission an independent review of the final diff")
    review.add_argument("--slice", required=True)
    review.add_argument("--skill", required=True, choices=["drift-audit", "code-review"])
    review.add_argument("--tool")
    review.add_argument("--model")
    review.add_argument("--effort")
    review.add_argument("--run")
    review.add_argument("--token")

    stop = subparsers.add_parser("stop", help="End the run, preserving evidence")
    stop.add_argument("--reason", required=True)
    stop.add_argument("--slice-status", choices=["stopped"])
    stop.add_argument("--scavenge", action="store_true")
    stop.add_argument("--run")
    stop.add_argument("--token")

    return parser


def _resolve_token(args: argparse.Namespace) -> str | None:
    token = getattr(args, "token", None)
    if token:
        return token
    return os.environ.get(_TOKEN_ENV_VAR)


def _run_check_plan(args: argparse.Namespace) -> int:
    plan_path = Path(args.plan)
    repo_path = Path(args.repo) if args.repo else None
    report = plan_mod.plan_check_report(plan_path, repo=repo_path)
    for error in report["errors"]:
        print(f"ERROR: {error}")
    for warning in report["warnings"]:
        print(f"WARNING: {warning}")
    gated = ", ".join(report["approval_gated"]) if report["approval_gated"] else "none"
    print(f"{report['slice_count']} slice(s); approval-gated: {gated}")
    return 0 if not report["errors"] else 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "check-plan":
            return _run_check_plan(args)
        if args.command in _NOT_YET_AVAILABLE:
            _resolve_token(args)  # plumbing exercised now; unused until wired
            raise PmError(f"{args.command} is not available yet (implemented in a later stage)")
        parser.error(f"unknown command: {args.command}")
        return 2
    except PmError as exc:
        print(f"pm: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
