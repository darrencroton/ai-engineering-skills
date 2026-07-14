from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import worker_contract


def load_worker_jobs():
    spec = importlib.util.spec_from_file_location("test_worker_jobs", SCRIPT_DIR / "worker_jobs.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkerContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / "target.py").write_text("print('ok')\n", encoding="utf-8")
        self.artifact_root = self.repo / ".worker-runs"
        self.run_dir = self.artifact_root / "workers-test"
        self.run_dir.mkdir(parents=True)
        self.policy = {
            "schema_version": 1,
            "run_id": "run-1",
            "slice_id": "Slice 1",
            "plan_sha256": "a" * 64,
            "repo_path": str(self.repo),
            "worker_artifact_root": str(self.artifact_root),
            "required_tools": ["opencode"],
            "allowed_roles": ["junior-worker", "senior-worker"],
            "required_model": "provider/model",
            "required_effort": "default",
            "allowed_access": ["read-only", "workspace-write"],
            "authorized_files": ["target.py"],
        }
        self.request = {
            "schema_version": 1,
            "label": "01-opencode-check-output",
            "slice_id": "Slice 1",
            "plan_sha256": "a" * 64,
            "tool": "opencode",
            "model": "provider/model",
            "effort": "default",
            "role": "junior-worker",
            "access": "read-only",
            "task": "Check the output.",
            "context": "A bounded validation task.",
            "required_skills": [],
            "files": ["target.py"],
            "constraints": ["Do not edit files."],
            "expected_output": "RESULT: pass or RESULT: blocked.",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_opencode_read_only_command_is_profile_composed(self):
        contract = worker_contract.validate_contract(self.policy, self.request, self.run_dir)
        prompt = worker_contract.render_worker_prompt(contract)
        command = worker_contract.compose_worker_command(contract, prompt)
        self.assertEqual(command[0:2], ["opencode", "run"])
        self.assertIn("--agent", command)
        self.assertEqual(command[command.index("--agent") + 1], "plan")
        self.assertIn("--auto", command)
        self.assertEqual(Path(command[command.index("--dir") + 1]), self.repo.resolve())
        self.assertIn("WORKER MODE: Delegated worker only", prompt)
        self.assertIn("no re-delegation", prompt)
        self.assertNotIn("<worker command>", " ".join(command))

    def test_prompt_defines_access_mode_semantics(self):
        # Regression: "Access mode is read-only; do not exceed it." left the
        # worker model to guess whether read-only forbids running commands.
        # OpenCode's plan agent only mechanically denies edit tools, and
        # models resolved the ambiguity inconsistently (MC Test 11), so the
        # prompt must state the contract semantics explicitly.
        contract = worker_contract.validate_contract(self.policy, self.request, self.run_dir)
        prompt = worker_contract.render_worker_prompt(contract)
        self.assertIn("run commands that do not modify the workspace", prompt)
        self.assertIn("must not create, edit, or delete files", prompt)

        self.request["access"] = "workspace-write"
        contract = worker_contract.validate_contract(self.policy, self.request, self.run_dir)
        prompt = worker_contract.render_worker_prompt(contract)
        self.assertIn("edit only the files listed in this request", prompt)

    def test_opencode_workspace_write_uses_build_agent(self):
        self.request["access"] = "workspace-write"
        contract = worker_contract.validate_contract(self.policy, self.request, self.run_dir)
        command = worker_contract.compose_worker_command(contract, "prompt")
        self.assertEqual(command[command.index("--agent") + 1], "build")

    def test_workspace_write_rejects_files_outside_authorized_surface(self):
        (self.repo / "other.py").write_text("print('no')\n", encoding="utf-8")
        self.request["access"] = "workspace-write"
        self.request["files"] = ["other.py"]
        with self.assertRaises(worker_contract.WorkerContractError) as raised:
            worker_contract.validate_contract(self.policy, self.request, self.run_dir)
        self.assertEqual(raised.exception.issues[0].code, "file-not-authorized")
        self.assertIn("revise the frozen plan", raised.exception.issues[0].correction)

    def test_authorized_surface_accepts_backtick_entry_with_trailing_annotation(self):
        # Regression: an authorized_files entry like "`target.py` (new file)"
        # was previously normalized to "target.py` (new file)" because
        # str.strip("`") only trims from the very ends of the string, so a
        # closing backtick followed by an annotation was never removed.
        self.policy["authorized_files"] = ["`target.py` (new file)"]
        self.request["access"] = "workspace-write"
        self.request["files"] = ["target.py"]
        contract = worker_contract.validate_contract(self.policy, self.request, self.run_dir)
        self.assertTrue(contract)

    def test_contract_mismatch_returns_actionable_corrections(self):
        self.request["slice_id"] = "Slice 2"
        self.request["model"] = "wrong/model"
        with self.assertRaises(worker_contract.WorkerContractError) as raised:
            worker_contract.validate_contract(self.policy, self.request, self.run_dir)
        issues = {issue.code: issue for issue in raised.exception.issues}
        self.assertIn("slice-mismatch", issues)
        self.assertIn("model-mismatch", issues)
        self.assertIn("Rewrite the request for Slice 1", issues["slice-mismatch"].correction)
        self.assertIn("provider/model", issues["model-mismatch"].correction)

    def test_reserved_skill_sets_rejects_mixed_request(self):
        # Regression: MC Test 2 found an orchestrator could draft a worker
        # request with required_skills mixing a reserved audit skill with
        # another value (or the other audit skill) instead of naming exactly
        # one. The policy-declared reserved_skill_sets rejects this before
        # any process starts.
        self.policy["reserved_skill_sets"] = [["drift-audit"], ["code-review"]]
        self.request["required_skills"] = ["drift-audit", "code-review"]
        with self.assertRaises(worker_contract.WorkerContractError) as raised:
            worker_contract.validate_contract(self.policy, self.request, self.run_dir)
        issues = {issue.code: issue for issue in raised.exception.issues}
        self.assertIn("reserved-skill-mismatch", issues)
        self.assertIn('["code-review"]', issues["reserved-skill-mismatch"].correction)
        self.assertIn('["drift-audit"]', issues["reserved-skill-mismatch"].correction)

    def test_reserved_skill_sets_accepts_exact_match(self):
        self.policy["reserved_skill_sets"] = [["drift-audit"], ["code-review"]]
        self.request["required_skills"] = ["drift-audit"]
        contract = worker_contract.validate_contract(self.policy, self.request, self.run_dir)
        self.assertEqual(contract["required_skills"], ["drift-audit"])

    def test_reserved_skill_sets_rejects_case_variant(self):
        # Regression: an independent review of this change found that the
        # intersection check compared skill names case-sensitively, so
        # required_skills: ["Drift-Audit"] matched neither the reserved-name
        # overlap test nor the exact-set match and silently passed pre-launch
        # validation instead of being rejected.
        self.policy["reserved_skill_sets"] = [["drift-audit"], ["code-review"]]
        self.request["required_skills"] = ["Drift-Audit"]
        with self.assertRaises(worker_contract.WorkerContractError) as raised:
            worker_contract.validate_contract(self.policy, self.request, self.run_dir)
        issues = {issue.code: issue for issue in raised.exception.issues}
        self.assertIn("reserved-skill-mismatch", issues)

    def test_reserved_skill_sets_does_not_block_unrelated_empty_request(self):
        # An empty required_skills is the valid shape for a bounded ad hoc
        # worker task unrelated to either audit; reserved_skill_sets must not
        # block it, since the pre-launch layer cannot distinguish that from a
        # misdrafted audit request (the finalize-time gate is the backstop
        # for that case).
        self.policy["reserved_skill_sets"] = [["drift-audit"], ["code-review"]]
        self.request["required_skills"] = []
        contract = worker_contract.validate_contract(self.policy, self.request, self.run_dir)
        self.assertEqual(contract["required_skills"], [])

    def test_reserved_skill_sets_fails_closed_on_malformed_top_level_value(self):
        # Regression: an independent review found that a malformed
        # reserved_skill_sets (wrong top-level type, e.g. corrupted policy
        # data) silently disabled the reservation entirely instead of
        # failing closed, since the old code only acted when the value was
        # already a well-formed list.
        self.policy["reserved_skill_sets"] = "drift-audit"
        self.request["required_skills"] = []
        with self.assertRaises(worker_contract.WorkerContractError) as raised:
            worker_contract.validate_contract(self.policy, self.request, self.run_dir)
        issues = {issue.code: issue for issue in raised.exception.issues}
        self.assertIn("policy-reserved-skill-sets-malformed", issues)

    def test_reserved_skill_sets_fails_closed_on_malformed_group(self):
        self.policy["reserved_skill_sets"] = [["drift-audit"], "code-review"]
        self.request["required_skills"] = []
        with self.assertRaises(worker_contract.WorkerContractError) as raised:
            worker_contract.validate_contract(self.policy, self.request, self.run_dir)
        issues = {issue.code: issue for issue in raised.exception.issues}
        self.assertIn("policy-reserved-skill-sets-malformed", issues)

    def test_reserved_skill_sets_rejection_propagates_through_launch_boundary(self):
        # Regression: prior tests only proved validate_contract rejects a
        # mismatched reserved-skill request directly; this proves the
        # rejection also propagates through worker_jobs.py's launch command
        # so no process is ever started, mirroring
        # test_rejected_launch_writes_feedback_and_starts_nothing.
        worker_jobs = load_worker_jobs()
        self.policy["reserved_skill_sets"] = [["drift-audit"], ["code-review"]]
        self.request["required_skills"] = ["drift-audit", "code-review"]
        policy_path = self.repo / "worker-policy.json"
        request_path = self.repo / "worker-request.json"
        policy_path.write_text(json.dumps(self.policy), encoding="utf-8")
        request_path.write_text(json.dumps(self.request), encoding="utf-8")
        worker_jobs.ensure_manifest(self.run_dir)
        args = mock.Mock(run_dir=str(self.run_dir), policy=str(policy_path), request=str(request_path), depends_on=None)
        with mock.patch.dict(os.environ, {worker_jobs.ARTIFACT_ROOT_ENV: str(self.artifact_root)}), mock.patch.object(
            worker_jobs, "start_tracked_worker"
        ) as start:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(worker_jobs.command_launch(args), 2)
        start.assert_not_called()
        feedback = json.loads((self.run_dir / f"{self.request['label']}-request-feedback.json").read_text())
        self.assertEqual(feedback["status"], "rejected")
        self.assertEqual(feedback["issues"][0]["code"], "reserved-skill-mismatch")

    def test_copilot_read_only_fails_closed(self):
        self.policy["required_tools"] = ["copilot"]
        self.policy["required_model"] = "default"
        self.request["tool"] = "copilot"
        self.request["model"] = "default"
        with self.assertRaises(worker_contract.WorkerContractError) as raised:
            worker_contract.validate_contract(self.policy, self.request, self.run_dir)
        self.assertEqual(raised.exception.issues[0].code, "unsupported-access")
        self.assertIn("cannot mechanically enforce", raised.exception.issues[0].message)

    def test_launch_records_validated_contract_and_artifacts(self):
        worker_jobs = load_worker_jobs()
        self.request["required_skills"] = ["drift-audit"]
        policy_path = self.repo / "worker-policy.json"
        request_path = self.repo / "worker-request.json"
        policy_path.write_text(json.dumps(self.policy), encoding="utf-8")
        request_path.write_text(json.dumps(self.request), encoding="utf-8")
        worker_jobs.ensure_manifest(self.run_dir)
        args = mock.Mock(run_dir=str(self.run_dir), policy=str(policy_path), request=str(request_path), depends_on=None)
        with mock.patch.dict(os.environ, {worker_jobs.ARTIFACT_ROOT_ENV: str(self.artifact_root)}), mock.patch.object(
            worker_jobs,
            "start_tracked_worker",
            return_value={"label": self.request["label"], "pid": 123, "run_dir": str(self.run_dir)},
        ) as start:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(worker_jobs.command_launch(args), 0)
        launch_contract = start.call_args.kwargs["launch_contract"]
        self.assertEqual(launch_contract["status"], "pass")
        self.assertEqual(launch_contract["access"], "read-only")
        self.assertEqual(launch_contract["required_skills"], ["drift-audit"])
        self.assertEqual(launch_contract["cwd"], str(self.repo.resolve()))
        self.assertEqual(start.call_args.kwargs["cwd"], self.repo.resolve())
        self.assertTrue((self.run_dir / f"{self.request['label']}-launch.json").is_file())
        self.assertTrue((self.run_dir / f"{self.request['label']}-prompt.md").is_file())

    def test_rejected_launch_writes_feedback_and_starts_nothing(self):
        worker_jobs = load_worker_jobs()
        self.request["slice_id"] = "Slice 2"
        policy_path = self.repo / "worker-policy.json"
        request_path = self.repo / "worker-request.json"
        policy_path.write_text(json.dumps(self.policy), encoding="utf-8")
        request_path.write_text(json.dumps(self.request), encoding="utf-8")
        worker_jobs.ensure_manifest(self.run_dir)
        args = mock.Mock(run_dir=str(self.run_dir), policy=str(policy_path), request=str(request_path), depends_on=None)
        with mock.patch.dict(os.environ, {worker_jobs.ARTIFACT_ROOT_ENV: str(self.artifact_root)}), mock.patch.object(
            worker_jobs, "start_tracked_worker"
        ) as start:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(worker_jobs.command_launch(args), 2)
        start.assert_not_called()
        feedback = json.loads((self.run_dir / f"{self.request['label']}-request-feedback.json").read_text())
        self.assertEqual(feedback["status"], "rejected")
        self.assertEqual(feedback["issues"][0]["code"], "slice-mismatch")
        self.assertIn("Correct only the listed", feedback["next_action"])

    def test_malformed_label_gets_actionable_feedback_without_starting(self):
        worker_jobs = load_worker_jobs()
        self.request["label"] = "BAD LABEL"
        policy_path = self.repo / "worker-policy.json"
        request_path = self.repo / "worker-request.json"
        policy_path.write_text(json.dumps(self.policy), encoding="utf-8")
        request_path.write_text(json.dumps(self.request), encoding="utf-8")
        worker_jobs.ensure_manifest(self.run_dir)
        args = mock.Mock(run_dir=str(self.run_dir), policy=str(policy_path), request=str(request_path), depends_on=None)
        with mock.patch.dict(os.environ, {worker_jobs.ARTIFACT_ROOT_ENV: str(self.artifact_root)}), mock.patch.object(
            worker_jobs, "start_tracked_worker"
        ) as start:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(worker_jobs.command_launch(args), 2)
        start.assert_not_called()
        feedback = json.loads((self.run_dir / "worker-request-request-feedback.json").read_text())
        self.assertEqual(feedback["issues"][0]["code"], "invalid-label")
        self.assertIn("01-opencode-check-output", feedback["issues"][0]["correction"])

    def test_required_skill_bundle_includes_transitive_markdown_references(self):
        bundle = worker_contract.compile_skill_bundle("ai-orchestrator")
        self.assertIn("BEGIN EMBEDDED SKILL FILE:", bundle)
        self.assertIn("# Deterministic Worker Contract", bundle)
        self.assertIn("worker_jobs.py launch", bundle)

    def test_missing_required_skill_fails_closed_before_launch(self):
        worker_jobs = load_worker_jobs()
        self.request["required_skills"] = ["not-installed-for-this-test"]
        policy_path = self.repo / "worker-policy.json"
        request_path = self.repo / "worker-request.json"
        policy_path.write_text(json.dumps(self.policy), encoding="utf-8")
        request_path.write_text(json.dumps(self.request), encoding="utf-8")
        worker_jobs.ensure_manifest(self.run_dir)
        args = mock.Mock(run_dir=str(self.run_dir), policy=str(policy_path), request=str(request_path), depends_on=None)
        with mock.patch.dict(os.environ, {worker_jobs.ARTIFACT_ROOT_ENV: str(self.artifact_root)}), mock.patch.object(
            worker_jobs, "start_tracked_worker"
        ) as start:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(worker_jobs.command_launch(args), 2)
        start.assert_not_called()
        feedback = json.loads((self.run_dir / f"{self.request['label']}-request-feedback.json").read_text())
        self.assertEqual(feedback["issues"][0]["code"], "required-skill-unavailable")

    def test_every_profile_uses_contract_repo_and_wrapper_enforces_cwd(self):
        cases = {
            "claude": ("read-only", "--add-dir"),
            "codex": ("read-only", "-C"),
            "copilot": ("workspace-write", "--add-dir"),
            "opencode": ("read-only", "--dir"),
        }
        for tool, (access, repo_flag) in cases.items():
            with self.subTest(tool=tool):
                policy = dict(self.policy, required_tools=[tool])
                request = dict(self.request, tool=tool, access=access)
                contract = worker_contract.validate_contract(policy, request, self.run_dir)
                command = worker_contract.compose_worker_command(contract, "prompt")
                self.assertEqual(Path(command[command.index(repo_flag) + 1]), self.repo.resolve())

        worker_jobs = load_worker_jobs()
        worker_jobs.ensure_manifest(self.run_dir)
        with mock.patch.object(worker_jobs.subprocess, "Popen") as popen:
            popen.return_value.pid = 123
            worker_jobs.start_tracked_worker(self.run_dir, "01-opencode-cwd-check", ["opencode", "run"], cwd=self.repo)
        wrapper = popen.call_args.args[0]
        self.assertEqual(Path(wrapper[wrapper.index("--cwd") + 1]), self.repo)

    def test_audit_skill_prompt_requires_machine_readable_verdict(self):
        self.request["required_skills"] = ["drift-audit"]
        contract = worker_contract.validate_contract(self.policy, self.request, self.run_dir)

        prompt = worker_contract.render_worker_prompt(contract)

        self.assertIn("MC_AUDIT_VERDICT: PASS | PASS WITH RISKS | FAIL | BLOCKED", prompt)
        self.assertTrue(prompt.rstrip().endswith("Use the verdict you actually reached; do not change it merely to satisfy the caller."))

    def test_worker_helper_extracts_exactly_one_audit_verdict(self):
        worker_jobs = load_worker_jobs()

        self.assertEqual(
            worker_jobs.audit_skill_verdicts(["code-review"], "report\nMC_AUDIT_VERDICT: PASS\n"),
            {"code-review": "PASS"},
        )
        self.assertEqual(
            worker_jobs.audit_skill_verdicts(["drift-audit"], "report without sentinel\n"),
            {"drift-audit": None},
        )

    def test_force_cancel_does_not_signal_reused_child_pid(self):
        worker_jobs = load_worker_jobs()
        status_file = self.run_dir / "01-opencode-check-status.json"
        status_file.write_text(
            json.dumps(
                {
                    "label": "01-opencode-check",
                    "state": "running",
                    "child_pid": 4242,
                    "child_identity": "original-start original-command",
                }
            ),
            encoding="utf-8",
        )
        entry = {
            "label": "01-opencode-check",
            "pid": 3131,
            "status_file": str(status_file),
        }

        with mock.patch.object(worker_jobs, "process_identity", return_value="reused-start unrelated-command"), mock.patch.object(
            worker_jobs, "tracked_wrapper_running", return_value=False
        ), mock.patch.object(worker_jobs.os, "killpg") as killpg:
            worker_jobs.force_cancel_entry(entry)

        killpg.assert_not_called()
        self.assertEqual(
            worker_jobs.audit_skill_verdicts(
                ["drift-audit"],
                "MC_AUDIT_VERDICT: FAIL\nMC_AUDIT_VERDICT: PASS\n",
            ),
            {"drift-audit": None},
        )

    def test_force_cancel_surfaces_permission_failure_without_claiming_cancelled(self):
        worker_jobs = load_worker_jobs()
        status_file = self.run_dir / "01-opencode-permission-status.json"
        status_file.write_text(
            json.dumps(
                {
                    "label": "01-opencode-permission",
                    "state": "running",
                    "child_pid": 4242,
                    "child_identity": "original-start",
                }
            ),
            encoding="utf-8",
        )
        entry = {"label": "01-opencode-permission", "pid": 3131, "status_file": str(status_file)}

        with mock.patch.object(worker_jobs, "process_identity", return_value="original-start"), mock.patch.object(
            worker_jobs.os, "getpgid", return_value=4242
        ), mock.patch.object(worker_jobs.os, "killpg", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                worker_jobs.force_cancel_entry(entry)

        status = json.loads(status_file.read_text(encoding="utf-8"))
        self.assertEqual(status["state"], "running")

    def test_cancel_terminates_identity_verified_orphan_child(self):
        worker_jobs = load_worker_jobs()
        worker_jobs.ensure_manifest(self.run_dir)
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            start_new_session=True,
        )
        try:
            status_file = self.run_dir / "01-opencode-orphan-child.status.json"
            outfile = self.run_dir / "01-opencode-orphan-child.stdout.log"
            errfile = self.run_dir / "01-opencode-orphan-child.stderr.log"
            worker_jobs.write_json(
                status_file,
                {
                    "label": "01-opencode-orphan-child",
                    "state": "running",
                    "child_pid": child.pid,
                    "child_identity": worker_jobs.process_identity(child.pid),
                },
            )
            manifest = worker_jobs.load_manifest(self.run_dir)
            manifest["workers"]["01-opencode-orphan-child"] = {
                "label": "01-opencode-orphan-child",
                "pid": 99999999,
                "status_file": str(status_file),
                "outfile": str(outfile),
                "errfile": str(errfile),
            }
            worker_jobs.save_manifest(self.run_dir, manifest)
            args = mock.Mock(run_dir=str(self.run_dir), label=None, timeout=2.0, interval=0.05, json=True)

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(worker_jobs.command_cancel(args), 0)

            child.wait(timeout=5)
            self.assertEqual(child.returncode, -signal.SIGTERM)
            status = json.loads(status_file.read_text(encoding="utf-8"))
            self.assertEqual(status["state"], "cancelled")
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=5)

    def test_cancel_attempts_remaining_workers_after_one_permission_failure(self):
        worker_jobs = load_worker_jobs()
        worker_jobs.ensure_manifest(self.run_dir)
        manifest = worker_jobs.load_manifest(self.run_dir)
        for index in (1, 2):
            label = f"0{index}-opencode-worker"
            status_file = self.run_dir / f"{label}-status.json"
            outfile = self.run_dir / f"{label}-out.txt"
            errfile = self.run_dir / f"{label}-err.txt"
            outfile.write_text("", encoding="utf-8")
            errfile.write_text("", encoding="utf-8")
            worker_jobs.write_json(status_file, {"label": label, "state": "running"})
            manifest["workers"][label] = {
                "label": label,
                "pid": 9000 + index,
                "status_file": str(status_file),
                "outfile": str(outfile),
                "errfile": str(errfile),
            }
        worker_jobs.save_manifest(self.run_dir, manifest)

        def force(entry):
            if entry["label"].startswith("01-"):
                raise PermissionError("denied")
            worker_jobs.mark_cancelled_entry(entry, forced=True, returncode=-signal.SIGKILL)

        args = mock.Mock(run_dir=str(self.run_dir), label=None, timeout=0.0, interval=0.01, json=True)
        with mock.patch.object(worker_jobs, "tracked_wrapper_running", return_value=False), mock.patch.object(
            worker_jobs, "tracked_child_running", return_value=True
        ), mock.patch.object(worker_jobs, "signal_tracked_child", return_value=True), mock.patch.object(
            worker_jobs, "force_cancel_entry", side_effect=force
        ) as force_cancel, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(worker_jobs.WorkerJobsError, "01-opencode-worker"):
                worker_jobs.command_cancel(args)

        self.assertEqual(force_cancel.call_count, 2)
        second_status = json.loads((self.run_dir / "02-opencode-worker-status.json").read_text(encoding="utf-8"))
        self.assertEqual(second_status["state"], "cancelled")


if __name__ == "__main__":
    unittest.main()
