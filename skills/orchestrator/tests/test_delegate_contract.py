from __future__ import annotations

import contextlib
import importlib.util
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

import delegate_contract


def load_delegate_jobs():
    spec = importlib.util.spec_from_file_location("test_delegate_jobs", SCRIPT_DIR / "delegate_jobs.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DelegateContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / "target.py").write_text("print('ok')\n", encoding="utf-8")
        self.artifact_root = self.repo / ".delegate-runs"
        self.run_dir = self.artifact_root / "delegates-test"
        self.run_dir.mkdir(parents=True)
        self.policy = {
            "schema_version": 3,
            "run_id": "run-1",
            "slice_id": "Slice 1",
            "plan_sha256": "a" * 64,
            "repo_path": str(self.repo),
            "delegate_artifact_root": str(self.artifact_root),
            "required_tools": ["opencode"],
            "required_model": "provider/model",
            "required_effort": "default",
            "required_access": ["read-only"],
        }
        self.request = {
            "schema_version": 3,
            "label": "01-opencode-check-output",
            "slice_id": "Slice 1",
            "plan_sha256": "a" * 64,
            "tool": "opencode",
            "model": "provider/model",
            "effort": "default",
            "access": "read-only",
            "task": "Check the output.",
            "context": "A bounded validation task.",
            "required_skills": [],
            "files": ["target.py"],
            "constraints": ["Cite the actual evidence."],
            "expected_output": "RESULT: pass or RESULT: blocked.",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def validate(self, *, tool: str = "opencode"):
        policy = dict(self.policy, required_tools=[tool])
        request = dict(self.request, tool=tool)
        return delegate_contract.validate_contract(policy, request, self.run_dir)

    def validate_write(self, *, tool: str = "opencode"):
        policy = dict(self.policy, required_tools=[tool], required_access=["read-only", "read-write"])
        request = dict(
            self.request,
            tool=tool,
            access="read-write",
            authorized_surface=["target.py"],
            non_goals=["Do not touch unrelated files."],
        )
        return delegate_contract.validate_contract(policy, request, self.run_dir)

    def test_normalized_contract_defaults_to_read_only_access(self):
        contract = self.validate()
        self.assertEqual(contract["schema_version"], 3)
        self.assertEqual(contract["access"], "read-only")
        self.assertEqual(contract["authorized_surface"], [])
        self.assertEqual(contract["non_goals"], [])
        self.assertNotIn("role", self.request)

    def test_read_write_request_is_authorized_and_normalizes_surface(self):
        contract = self.validate_write()
        self.assertEqual(contract["access"], "read-write")
        self.assertEqual(contract["authorized_surface"], ["target.py"])
        self.assertEqual(contract["non_goals"], ["Do not touch unrelated files."])

    def test_read_write_request_requires_nonempty_authorized_surface(self):
        policy = dict(self.policy, required_access=["read-only", "read-write"])
        request = dict(self.request, access="read-write")
        with self.assertRaises(delegate_contract.DelegateContractError) as raised:
            delegate_contract.validate_contract(policy, request, self.run_dir)
        issues = {issue.field: issue for issue in raised.exception.issues}
        self.assertIn("authorized_surface", issues)
        self.assertEqual(issues["authorized_surface"].code, "missing-field")

    def test_read_only_request_rejects_authorized_surface_and_non_goals(self):
        request = dict(self.request, authorized_surface=["target.py"], non_goals=["none"])
        with self.assertRaises(delegate_contract.DelegateContractError) as raised:
            delegate_contract.validate_contract(self.policy, request, self.run_dir)
        codes = {issue.field: issue.code for issue in raised.exception.issues}
        self.assertEqual(codes.get("authorized_surface"), "field-not-applicable")
        self.assertEqual(codes.get("non_goals"), "field-not-applicable")

    def test_read_only_request_rejects_explicitly_empty_authorized_surface(self):
        # An empty list is still a write-mode field placed on a read-only
        # request: rejection must key off presence in the raw payload, not
        # truthiness of the parsed list, or an explicit [] silently passes.
        request = dict(self.request, authorized_surface=[], non_goals=[])
        with self.assertRaises(delegate_contract.DelegateContractError) as raised:
            delegate_contract.validate_contract(self.policy, request, self.run_dir)
        codes = {issue.field: issue.code for issue in raised.exception.issues}
        self.assertEqual(codes.get("authorized_surface"), "field-not-applicable")
        self.assertEqual(codes.get("non_goals"), "field-not-applicable")

    def test_read_write_request_requires_nonempty_non_goals(self):
        policy = dict(self.policy, required_access=["read-only", "read-write"])
        request = dict(self.request, access="read-write", authorized_surface=["target.py"], non_goals=[])
        with self.assertRaises(delegate_contract.DelegateContractError) as raised:
            delegate_contract.validate_contract(policy, request, self.run_dir)
        issues = {issue.field: issue for issue in raised.exception.issues}
        self.assertIn("non_goals", issues)
        self.assertEqual(issues["non_goals"].code, "missing-field")

    def test_access_must_be_authorized_by_policy(self):
        request = dict(
            self.request,
            access="read-write",
            authorized_surface=["target.py"],
            non_goals=[],
        )
        with self.assertRaises(delegate_contract.DelegateContractError) as raised:
            delegate_contract.validate_contract(self.policy, request, self.run_dir)
        issue = raised.exception.issues[0]
        self.assertEqual(issue.code, "access-not-authorized")
        self.assertEqual(issue.field, "access")

    def test_request_rejects_retired_role_and_write_fields(self):
        for field, value in (
            ("role", "senior-reviewer"),
            ("worker_role", "junior-worker"),
            ("authorized_files", ["target.py"]),
        ):
            with self.subTest(field=field):
                request = dict(self.request, **{field: value})
                with self.assertRaises(delegate_contract.DelegateContractError) as raised:
                    delegate_contract.validate_contract(self.policy, request, self.run_dir)
                self.assertEqual(raised.exception.issues[0].code, "unknown-field")
                self.assertEqual(raised.exception.issues[0].field, f"request.{field}")

    def test_never_delegate_skills_are_rejected_in_either_access_mode(self):
        for skill in ("commit", "orchestrator", "project-manager", "scoped-implementation"):
            with self.subTest(skill=skill):
                request = dict(self.request, required_skills=[skill])
                with self.assertRaises(delegate_contract.DelegateContractError) as raised:
                    delegate_contract.validate_contract(self.policy, request, self.run_dir)
                issue = raised.exception.issues[0]
                self.assertEqual(issue.code, "skill-not-permitted")
                self.assertEqual(issue.field, "required_skills[0]")

                write_request = dict(
                    self.request,
                    required_skills=[skill],
                    access="read-write",
                    authorized_surface=["target.py"],
                    non_goals=["none"],
                )
                write_policy = dict(self.policy, required_access=["read-only", "read-write"])
                with self.assertRaises(delegate_contract.DelegateContractError) as raised:
                    delegate_contract.validate_contract(write_policy, write_request, self.run_dir)
                self.assertEqual(raised.exception.issues[0].code, "skill-not-permitted")

    def test_write_only_skill_is_read_write_only(self):
        read_only_request = dict(self.request, required_skills=["code-simplifier"])
        with self.assertRaises(delegate_contract.DelegateContractError) as raised:
            delegate_contract.validate_contract(self.policy, read_only_request, self.run_dir)
        issue = raised.exception.issues[0]
        self.assertEqual(issue.code, "skill-not-permitted-for-access")
        self.assertEqual(issue.field, "required_skills[0]")

        write_policy = dict(self.policy, required_access=["read-only", "read-write"])
        write_request = dict(
            self.request,
            required_skills=["code-simplifier"],
            access="read-write",
            authorized_surface=["target.py"],
            non_goals=["none"],
        )
        contract = delegate_contract.validate_contract(write_policy, write_request, self.run_dir)
        self.assertEqual(contract["required_skills"], ["code-simplifier"])

    def test_malformed_skill_name_is_rejected(self):
        for skill in ("../../etc/passwd", "Code-Review", "code_review", "/etc/passwd", ""):
            with self.subTest(skill=skill or "(empty)"):
                request = dict(self.request, required_skills=[skill] if skill else [""])
                with self.assertRaises(delegate_contract.DelegateContractError) as raised:
                    delegate_contract.validate_contract(self.policy, request, self.run_dir)
                codes = {issue.code for issue in raised.exception.issues}
                # An empty string is caught earlier by _string_list's
                # non-empty-item check; every other case must fail the skill
                # name format check specifically.
                self.assertTrue(codes & {"invalid-skill-name", "wrong-type"})

    def test_request_rejects_unsupported_access_value(self):
        request = dict(self.request, access="workspace-write")
        with self.assertRaises(delegate_contract.DelegateContractError) as raised:
            delegate_contract.validate_contract(self.policy, request, self.run_dir)
        issue = raised.exception.issues[0]
        self.assertEqual(issue.code, "unsupported-access")
        self.assertEqual(issue.field, "access")

    def test_request_requires_explicit_tool_model_effort_and_access(self):
        for field in ("tool", "model", "effort", "access"):
            with self.subTest(field=field):
                request = dict(self.request)
                del request[field]
                with self.assertRaises(delegate_contract.DelegateContractError) as raised:
                    delegate_contract.validate_contract(self.policy, request, self.run_dir)
                self.assertIn(
                    field,
                    {issue.field for issue in raised.exception.issues if issue.code == "missing-field"},
                )

    def test_policy_rejects_retired_and_unknown_fields(self):
        for field, value in (
            ("worker_artifact_root", str(self.artifact_root)),
            ("allowed_roles", ["reviewer"]),
            ("allowed_access", ["read-only"]),
            ("authorized_files", ["target.py"]),
            ("extension", True),
        ):
            with self.subTest(field=field):
                policy = dict(self.policy, **{field: value})
                with self.assertRaises(delegate_contract.DelegateContractError) as raised:
                    delegate_contract.validate_contract(policy, self.request, self.run_dir)
                self.assertEqual(raised.exception.issues[0].code, "unknown-field")
                self.assertEqual(raised.exception.issues[0].field, f"policy.{field}")

    def test_policy_rejects_unsupported_required_access_value(self):
        policy = dict(self.policy, required_access=["read-only", "write-anything"])
        with self.assertRaises(delegate_contract.DelegateContractError) as raised:
            delegate_contract.validate_contract(policy, self.request, self.run_dir)
        issue = raised.exception.issues[0]
        self.assertEqual(issue.code, "unsupported-access")
        self.assertEqual(issue.field, "required_access[1]")

    def test_schema_v2_is_rejected_for_policy_and_request(self):
        for target in ("policy", "request"):
            policy = dict(self.policy)
            request = dict(self.request)
            (policy if target == "policy" else request)["schema_version"] = 2
            with self.assertRaises(delegate_contract.DelegateContractError) as raised:
                delegate_contract.validate_contract(policy, request, self.run_dir)
            self.assertIn("schema-version", {issue.code for issue in raised.exception.issues})

    def test_schema_v2_run_manifest_is_rejected_without_migration(self):
        delegate_jobs = load_delegate_jobs()
        delegate_jobs.write_json(
            self.run_dir / delegate_jobs.MANIFEST_NAME,
            {"schema_version": 2, "delegates": {}},
        )
        with self.assertRaisesRegex(delegate_jobs.DelegateJobsError, "Start a new .orchestrator run"):
            delegate_jobs.ensure_manifest(self.run_dir)

    def test_every_harness_is_delegate_eligible_and_uses_contract_repo(self):
        repo_flags = {
            "claude": "--add-dir",
            "codex": "-C",
            "copilot": "--add-dir",
            "opencode": "--dir",
            "qwen": None,
        }
        for tool, repo_flag in repo_flags.items():
            with self.subTest(tool=tool):
                contract = self.validate(tool=tool)
                command = delegate_contract.compose_delegate_command(contract, "prompt")
                if repo_flag is None:
                    self.assertEqual(command[:2], ["qwen", "--prompt"])
                else:
                    self.assertEqual(Path(command[command.index(repo_flag) + 1]), self.repo.resolve())

        self.assertEqual(set(delegate_contract.DELEGATE_PROFILES), set(repo_flags))
        self.assertEqual(
            delegate_contract.DELEGATE_PROFILES["copilot"]["read_only_enforcement"],
            "prompt-enforced",
        )

    def test_harness_commands_select_only_read_only_modes_by_default(self):
        cases = {
            "claude": ("--permission-mode", "plan"),
            "codex": ("--sandbox", "read-only"),
            "opencode": ("--agent", "plan"),
            "qwen": ("--sandbox", "--output-format"),
        }
        for tool, (flag, expected) in cases.items():
            with self.subTest(tool=tool):
                command = delegate_contract.compose_delegate_command(self.validate(tool=tool), "prompt")
                if tool == "qwen":
                    self.assertIn(flag, command)
                    self.assertEqual(command[command.index(expected) + 1], "text")
                else:
                    self.assertEqual(command[command.index(flag) + 1], expected)
                self.assertNotIn("acceptEdits", command)
                self.assertNotIn("workspace-write", command)
                self.assertNotIn("build", command)

        copilot = delegate_contract.compose_delegate_command(self.validate(tool="copilot"), "prompt")
        self.assertIn("--autopilot", copilot)

    def test_settable_harness_commands_include_generated_session_id(self):
        session_id = "12345678-1234-1234-1234-123456789abc"
        with mock.patch.object(delegate_contract.uuid, "uuid4", return_value=session_id):
            for tool in ("claude", "copilot"):
                with self.subTest(tool=tool):
                    command = delegate_contract.compose_delegate_command(self.validate(tool=tool), "prompt")
                    self.assertEqual(command[command.index("--session-id") + 1], session_id)

        for tool in ("codex", "opencode", "qwen"):
            with self.subTest(tool=tool):
                command = delegate_contract.compose_delegate_command(self.validate(tool=tool), "prompt")
                self.assertNotIn("--session-id", command)

    def test_harness_commands_select_write_enabled_modes(self):
        cases = {
            "claude": ("--permission-mode", "acceptEdits"),
            "codex": ("--sandbox", "workspace-write"),
            "opencode": ("--agent", "build"),
        }
        for tool, (flag, expected) in cases.items():
            with self.subTest(tool=tool):
                command = delegate_contract.compose_delegate_command(self.validate_write(tool=tool), "prompt")
                self.assertEqual(command[command.index(flag) + 1], expected)

        # Copilot and Qwen have no tested mechanical write-enabled flag distinct
        # from their read-only command; access is entirely prompt-enforced for
        # both, so the composed command is identical either way.
        for tool in ("copilot", "qwen"):
            with self.subTest(tool=tool):
                with mock.patch.object(delegate_contract.uuid, "uuid4", return_value="12345678-1234-1234-1234-123456789abc"):
                    read_only_command = delegate_contract.compose_delegate_command(self.validate(tool=tool), "prompt")
                    write_command = delegate_contract.compose_delegate_command(self.validate_write(tool=tool), "prompt")
                self.assertEqual(read_only_command, write_command)

    def test_opencode_nondefault_effort_fails_closed(self):
        policy = dict(self.policy, required_effort="high")
        request = dict(self.request, effort="high")
        contract = delegate_contract.validate_contract(policy, request, self.run_dir)
        with self.assertRaises(delegate_contract.DelegateContractError) as raised:
            delegate_contract.compose_delegate_command(contract, "prompt")
        self.assertEqual(raised.exception.issues[0].code, "unsupported-effort")
        self.assertEqual(raised.exception.issues[0].field, "effort")

    def test_qwen_nondefault_effort_fails_closed(self):
        policy = dict(self.policy, required_tools=["qwen"], required_effort="high")
        request = dict(self.request, tool="qwen", effort="high")
        contract = delegate_contract.validate_contract(policy, request, self.run_dir)
        with self.assertRaises(delegate_contract.DelegateContractError) as raised:
            delegate_contract.compose_delegate_command(contract, "prompt")
        self.assertEqual(raised.exception.issues[0].code, "unsupported-effort")
        self.assertEqual(raised.exception.issues[0].field, "effort")

    def test_prompt_intrinsically_forbids_mutation_for_read_only_delegate(self):
        for tool in delegate_contract.DELEGATE_PROFILES:
            with self.subTest(tool=tool):
                prompt = delegate_contract.render_delegate_prompt(self.validate(tool=tool))
                self.assertIn("ACCESS: read-only", prompt)
                self.assertIn("must not create, edit, delete, move, or format files", prompt)
                self.assertIn("Do not run tests or commands that may write", prompt)
                self.assertIn("Do not perform Git, GitHub, commit, branch, staging, push", prompt)
                self.assertIn("Do not invoke orchestrator, re-delegate", prompt)

    def test_prompt_read_write_includes_authorized_surface_and_forbids_git_mutations(self):
        prompt = delegate_contract.render_delegate_prompt(self.validate_write())
        self.assertIn("ACCESS: read-write", prompt)
        self.assertIn("AUTHORIZED SURFACE:", prompt)
        self.assertIn("target.py", prompt)
        self.assertIn("NON-GOALS:", prompt)
        self.assertIn("Do not touch unrelated files.", prompt)
        self.assertIn("Do not perform Git, GitHub, commit, branch, staging, push", prompt)
        self.assertIn("Do not invoke orchestrator", prompt)
        self.assertIn("only inside the authorized surface", prompt)

    def test_contract_mismatch_returns_actionable_corrections(self):
        self.request["slice_id"] = "Slice 2"
        self.request["model"] = "wrong/model"
        with self.assertRaises(delegate_contract.DelegateContractError) as raised:
            delegate_contract.validate_contract(self.policy, self.request, self.run_dir)
        issues = {issue.code: issue for issue in raised.exception.issues}
        self.assertIn("slice-mismatch", issues)
        self.assertIn("model-mismatch", issues)
        self.assertIn("Rewrite the request for Slice 1", issues["slice-mismatch"].correction)
        self.assertIn("provider/model", issues["model-mismatch"].correction)

    def test_missing_and_outside_inputs_fail_closed(self):
        self.request["files"] = ["missing.py", "../outside.py"]
        with self.assertRaises(delegate_contract.DelegateContractError) as raised:
            delegate_contract.validate_contract(self.policy, self.request, self.run_dir)
        codes = {issue.code for issue in raised.exception.issues}
        self.assertIn("missing-input", codes)
        self.assertIn("path-outside-repo", codes)

    def test_launch_records_schema_v3_normalized_evidence_and_artifacts(self):
        delegate_jobs = load_delegate_jobs()
        self.request["required_skills"] = ["drift-audit"]
        policy_path = self.repo / "delegate-policy.json"
        request_path = self.repo / "delegate-request.json"
        policy_path.write_text(json.dumps(self.policy), encoding="utf-8")
        request_path.write_text(json.dumps(self.request), encoding="utf-8")
        delegate_jobs.ensure_manifest(self.run_dir)
        args = mock.Mock(run_dir=str(self.run_dir), policy=str(policy_path), request=str(request_path), depends_on=None)
        with mock.patch.dict(os.environ, {delegate_jobs.ARTIFACT_ROOT_ENV: str(self.artifact_root)}), mock.patch.object(
            delegate_jobs,
            "start_tracked_delegate",
            return_value={"label": self.request["label"], "pid": 123, "run_dir": str(self.run_dir)},
        ) as start, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(delegate_jobs.command_launch(args), 0)

        evidence = start.call_args.kwargs["launch_contract"]
        self.assertEqual(evidence["schema_version"], 3)
        self.assertNotIn("role", evidence)
        self.assertEqual(evidence["access"], "read-only")
        self.assertEqual(evidence["authorized_surface"], [])
        self.assertEqual(evidence["required_skills"], ["drift-audit"])
        self.assertEqual(evidence["cwd"], str(self.repo.resolve()))
        self.assertTrue((self.run_dir / f"{self.request['label']}-launch.json").is_file())
        self.assertTrue((self.run_dir / f"{self.request['label']}-prompt.md").is_file())

    def test_launch_records_read_write_surface_and_non_goals_evidence(self):
        delegate_jobs = load_delegate_jobs()
        policy = dict(self.policy, required_access=["read-only", "read-write"])
        request = dict(
            self.request,
            access="read-write",
            authorized_surface=["target.py: add a helper"],
            non_goals=["Do not touch any other file."],
        )
        policy_path = self.repo / "delegate-policy.json"
        request_path = self.repo / "delegate-request.json"
        policy_path.write_text(json.dumps(policy), encoding="utf-8")
        request_path.write_text(json.dumps(request), encoding="utf-8")
        delegate_jobs.ensure_manifest(self.run_dir)
        args = mock.Mock(run_dir=str(self.run_dir), policy=str(policy_path), request=str(request_path), depends_on=None)
        with mock.patch.dict(os.environ, {delegate_jobs.ARTIFACT_ROOT_ENV: str(self.artifact_root)}), mock.patch.object(
            delegate_jobs,
            "start_tracked_delegate",
            return_value={"label": request["label"], "pid": 123, "run_dir": str(self.run_dir)},
        ) as start, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(delegate_jobs.command_launch(args), 0)

        evidence = start.call_args.kwargs["launch_contract"]
        self.assertEqual(evidence["access"], "read-write")
        self.assertEqual(evidence["authorized_surface"], ["target.py: add a helper"])
        self.assertEqual(evidence["non_goals"], ["Do not touch any other file."])
        prompt_text = (self.run_dir / f"{request['label']}-prompt.md").read_text(encoding="utf-8")
        self.assertIn("ACCESS: read-write", prompt_text)
        self.assertIn("target.py: add a helper", prompt_text)

    def test_tracked_launch_persists_session_metadata_for_every_harness(self):
        delegate_jobs = load_delegate_jobs()
        delegate_jobs.ensure_manifest(self.run_dir)
        session_id = "12345678-1234-1234-1234-123456789abc"
        commands = {
            "claude": ["claude", "-p", "prompt", "--session-id", session_id],
            "codex": ["codex", "exec", "prompt", "-C", str(self.repo)],
            "copilot": ["copilot", "-p", "prompt", "--session-id", session_id],
            "opencode": ["opencode", "run", "prompt", "--dir", str(self.repo)],
            "qwen": ["qwen", "--prompt", "prompt"],
        }
        captured_ids = {
            "claude": session_id,
            "codex": "22345678-1234-1234-1234-123456789abc",
            "copilot": session_id,
            "opencode": "ses_owned",
            "qwen": "32345678-1234-1234-1234-123456789abc",
        }
        process = mock.Mock(pid=4242)

        def resolved(entry, *, wait_seconds):
            self.assertEqual(wait_seconds, 5.0)
            return captured_ids[entry["tool"]], self.root / f"{entry['tool']}.jsonl"

        with mock.patch.object(delegate_jobs.subprocess, "Popen", return_value=process), mock.patch.object(
            delegate_jobs, "resolve_launch_session", side_effect=resolved
        ), mock.patch.object(delegate_jobs, "sync_run_index"):
            for index, (tool, command) in enumerate(commands.items(), start=1):
                result = delegate_jobs.start_tracked_delegate(
                    self.run_dir,
                    f"0{index}-{tool}-capture",
                    command,
                    cwd=self.repo,
                )
                self.assertEqual(result["session_id"], captured_ids[tool])

        manifest = delegate_jobs.load_manifest(self.run_dir)
        self.assertEqual(len(manifest["delegates"]), 5)
        for entry in manifest["delegates"].values():
            self.assertIn("session_id", entry)
            self.assertEqual(entry["session_id"], captured_ids[entry["tool"]])
            self.assertEqual(entry["session_path"], str(self.root / f"{entry['tool']}.jsonl"))

    def test_tracked_launch_succeeds_with_null_when_post_launch_capture_fails(self):
        delegate_jobs = load_delegate_jobs()
        delegate_jobs.ensure_manifest(self.run_dir)
        process = mock.Mock(pid=4242)
        label = "01-qwen-capture"
        with mock.patch.object(delegate_jobs.subprocess, "Popen", return_value=process), mock.patch.object(
            delegate_jobs, "resolve_launch_session", side_effect=OSError("store unavailable")
        ), mock.patch.object(delegate_jobs, "sync_run_index"), contextlib.redirect_stderr(io.StringIO()) as stderr:
            result = delegate_jobs.start_tracked_delegate(self.run_dir, label, ["qwen", "--prompt", "prompt"], cwd=self.repo)

        self.assertIsNone(result["session_id"])
        self.assertIn("session capture failed", stderr.getvalue())
        entry = delegate_jobs.load_manifest(self.run_dir)["delegates"][label]
        self.assertIn("session_id", entry)
        self.assertIsNone(entry["session_id"])
        self.assertNotIn("session_path", entry)

    def test_tracked_launch_preserves_settable_id_when_capture_fails(self):
        delegate_jobs = load_delegate_jobs()
        delegate_jobs.ensure_manifest(self.run_dir)
        process = mock.Mock(pid=4242)
        session_id = "12345678-1234-1234-1234-123456789abc"
        with mock.patch.object(delegate_jobs.subprocess, "Popen", return_value=process), mock.patch.object(
            delegate_jobs, "resolve_launch_session", side_effect=OSError("store unavailable")
        ), mock.patch.object(delegate_jobs, "sync_run_index"), contextlib.redirect_stderr(io.StringIO()):
            for index, tool in enumerate(("claude", "copilot"), start=1):
                label = f"0{index}-{tool}-capture"
                result = delegate_jobs.start_tracked_delegate(
                    self.run_dir,
                    label,
                    [tool, "-p", "prompt", "--session-id", session_id],
                    cwd=self.repo,
                )
                self.assertEqual(result["session_id"], session_id)
                entry = delegate_jobs.load_manifest(self.run_dir)["delegates"][label]
                self.assertEqual(entry["session_id"], session_id)

    def test_status_and_activity_json_surface_session_id_for_every_harness(self):
        delegate_jobs = load_delegate_jobs()
        manifest = delegate_jobs.ensure_manifest(self.run_dir)
        session_ids = {}
        for index, tool in enumerate(("claude", "codex", "copilot", "opencode", "qwen"), start=1):
            label = f"0{index}-{tool}-capture"
            session_ids[label] = f"session-{tool}"
            manifest["delegates"][label] = {
                "label": label,
                "tool": tool,
                "pid": 9000 + index,
                "session_id": session_ids[label],
                "status_file": str(self.run_dir / f"{label}-status.json"),
                "outfile": str(self.run_dir / f"{label}-out.txt"),
                "errfile": str(self.run_dir / f"{label}-err.txt"),
                "command": [tool],
            }
        delegate_jobs.save_manifest(self.run_dir, manifest)

        def status(entry):
            return {
                "label": entry["label"],
                "pid": entry["pid"],
                "tool": entry["tool"],
                "state": "running",
                "running": True,
                "outfile_size": 0,
                "errfile_size": 0,
                "returncode": None,
                "session_id": entry["session_id"],
            }

        status_args = mock.Mock(run_dir=str(self.run_dir), label=None, json=True)
        activity_args = mock.Mock(run_dir=str(self.run_dir), label=None, json=True, max_idle=60)
        with mock.patch.object(delegate_jobs, "delegate_status", side_effect=status), contextlib.redirect_stdout(
            io.StringIO()
        ) as output:
            self.assertEqual(delegate_jobs.command_status(status_args), 0)
        status_rows = json.loads(output.getvalue())
        self.assertEqual({row["label"]: row["session_id"] for row in status_rows}, session_ids)

        with mock.patch.object(delegate_jobs, "delegate_status", side_effect=status), mock.patch.object(
            delegate_jobs, "resolve_session_path", return_value=None
        ), mock.patch.object(delegate_jobs, "helper_activity", return_value={}), contextlib.redirect_stdout(
            io.StringIO()
        ) as output:
            self.assertEqual(delegate_jobs.command_activity(activity_args), 0)
        activity_rows = json.loads(output.getvalue())
        self.assertEqual({row["label"]: row["session_id"] for row in activity_rows}, session_ids)

    def test_rejected_launch_writes_feedback_and_starts_nothing(self):
        delegate_jobs = load_delegate_jobs()
        self.request["role"] = "reviewer"
        policy_path = self.repo / "delegate-policy.json"
        request_path = self.repo / "delegate-request.json"
        policy_path.write_text(json.dumps(self.policy), encoding="utf-8")
        request_path.write_text(json.dumps(self.request), encoding="utf-8")
        delegate_jobs.ensure_manifest(self.run_dir)
        args = mock.Mock(run_dir=str(self.run_dir), policy=str(policy_path), request=str(request_path), depends_on=None)
        with mock.patch.dict(os.environ, {delegate_jobs.ARTIFACT_ROOT_ENV: str(self.artifact_root)}), mock.patch.object(
            delegate_jobs, "start_tracked_delegate"
        ) as start, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(delegate_jobs.command_launch(args), 2)
        start.assert_not_called()
        feedback = json.loads((self.run_dir / f"{self.request['label']}-request-feedback.json").read_text())
        self.assertEqual(feedback["issues"][0]["code"], "unknown-field")

    def test_required_skill_bundle_includes_transitive_markdown_references(self):
        bundle = delegate_contract.compile_skill_bundle("orchestrator")
        self.assertIn("# Deterministic Delegate Contract", bundle)
        self.assertIn("delegate_jobs.py launch", bundle)

    def test_delegate_status_dead_wrapper_without_status_payload_is_failed(self):
        delegate_jobs = load_delegate_jobs()
        entry = {
            "label": "01-opencode-check",
            "pid": 999999,
            "tool": "opencode",
            "status_file": str(self.run_dir / "01-opencode-check-status.json"),
            "outfile": str(self.run_dir / "01-opencode-check.out"),
            "errfile": str(self.run_dir / "01-opencode-check.err"),
            "started_at": "2026-01-01T00:00:00Z",
            "command": ["opencode"],
        }

        with mock.patch.object(delegate_jobs, "process_running", return_value=False):
            status = delegate_jobs.delegate_status(entry)

        self.assertFalse(status["running"])
        self.assertEqual(status["state"], "failed")

    def test_command_wait_exits_nonzero_for_dead_wrapper_without_status_payload(self):
        delegate_jobs = load_delegate_jobs()
        entry = {
            "label": "01-opencode-check",
            "pid": 999999,
            "tool": "opencode",
            "status_file": str(self.run_dir / "01-opencode-check-status.json"),
            "outfile": str(self.run_dir / "01-opencode-check.out"),
            "errfile": str(self.run_dir / "01-opencode-check.err"),
            "started_at": "2026-01-01T00:00:00Z",
            "command": ["opencode"],
        }
        manifest = delegate_jobs.ensure_manifest(self.run_dir)
        manifest["delegates"][entry["label"]] = entry
        delegate_jobs.save_manifest(self.run_dir, manifest)
        args = mock.Mock(run_dir=str(self.run_dir), label=None, timeout=None, interval=0, json=False)

        with mock.patch.object(delegate_jobs, "process_running", return_value=False), contextlib.redirect_stdout(
            io.StringIO()
        ):
            # A wrapper that died before writing *-status.json must not report
            # exit 0 ("success") from wait: PM's evidence gate still rejects
            # such a slice, so a 0 here would mislead any caller trusting the
            # helper's exit code instead of the gate.
            self.assertEqual(delegate_jobs.command_wait(args), 1)

    def test_force_cancel_does_not_signal_reused_child_pid(self):
        delegate_jobs = load_delegate_jobs()
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

        with mock.patch.object(delegate_jobs, "process_identity", return_value="reused-start unrelated-command"), mock.patch.object(
            delegate_jobs, "tracked_wrapper_running", return_value=False
        ), mock.patch.object(delegate_jobs.os, "killpg") as killpg:
            delegate_jobs.force_cancel_entry(entry)

        killpg.assert_not_called()

    def test_force_cancel_surfaces_permission_failure_without_claiming_cancelled(self):
        delegate_jobs = load_delegate_jobs()
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

        with mock.patch.object(delegate_jobs, "process_identity", return_value="original-start"), mock.patch.object(
            delegate_jobs.os, "getpgid", return_value=4242
        ), mock.patch.object(delegate_jobs.os, "killpg", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                delegate_jobs.force_cancel_entry(entry)

        status = json.loads(status_file.read_text(encoding="utf-8"))
        self.assertEqual(status["state"], "running")

    def test_cancel_terminates_identity_verified_orphan_child(self):
        delegate_jobs = load_delegate_jobs()
        delegate_jobs.ensure_manifest(self.run_dir)
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            start_new_session=True,
        )
        try:
            status_file = self.run_dir / "01-opencode-orphan-child.status.json"
            outfile = self.run_dir / "01-opencode-orphan-child.stdout.log"
            errfile = self.run_dir / "01-opencode-orphan-child.stderr.log"
            delegate_jobs.write_json(
                status_file,
                {
                    "label": "01-opencode-orphan-child",
                    "state": "running",
                    "child_pid": child.pid,
                    "child_identity": delegate_jobs.process_identity(child.pid),
                },
            )
            manifest = delegate_jobs.load_manifest(self.run_dir)
            manifest["delegates"]["01-opencode-orphan-child"] = {
                "label": "01-opencode-orphan-child",
                "pid": 99999999,
                "status_file": str(status_file),
                "outfile": str(outfile),
                "errfile": str(errfile),
            }
            delegate_jobs.save_manifest(self.run_dir, manifest)
            args = mock.Mock(run_dir=str(self.run_dir), label=None, timeout=2.0, interval=0.05, json=True)

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(delegate_jobs.command_cancel(args), 0)

            child.wait(timeout=5)
            self.assertEqual(child.returncode, -signal.SIGTERM)
            status = json.loads(status_file.read_text(encoding="utf-8"))
            self.assertEqual(status["state"], "cancelled")
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=5)

    def test_cancel_attempts_remaining_delegates_after_one_permission_failure(self):
        delegate_jobs = load_delegate_jobs()
        delegate_jobs.ensure_manifest(self.run_dir)
        manifest = delegate_jobs.load_manifest(self.run_dir)
        for index in (1, 2):
            label = f"0{index}-opencode-check"
            status_file = self.run_dir / f"{label}-status.json"
            outfile = self.run_dir / f"{label}-out.txt"
            errfile = self.run_dir / f"{label}-err.txt"
            outfile.write_text("", encoding="utf-8")
            errfile.write_text("", encoding="utf-8")
            delegate_jobs.write_json(status_file, {"label": label, "state": "running"})
            manifest["delegates"][label] = {
                "label": label,
                "pid": 9000 + index,
                "status_file": str(status_file),
                "outfile": str(outfile),
                "errfile": str(errfile),
            }
        delegate_jobs.save_manifest(self.run_dir, manifest)

        def force(entry):
            if entry["label"].startswith("01-"):
                raise PermissionError("denied")
            delegate_jobs.mark_cancelled_entry(entry, forced=True, returncode=-signal.SIGKILL)

        args = mock.Mock(run_dir=str(self.run_dir), label=None, timeout=0.0, interval=0.01, json=True)
        with mock.patch.object(delegate_jobs, "tracked_wrapper_running", return_value=False), mock.patch.object(
            delegate_jobs, "tracked_child_running", return_value=True
        ), mock.patch.object(delegate_jobs, "signal_tracked_child", return_value=True), mock.patch.object(
            delegate_jobs, "force_cancel_entry", side_effect=force
        ) as force_cancel, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(delegate_jobs.DelegateJobsError, "01-opencode-check"):
                delegate_jobs.command_cancel(args)

        self.assertEqual(force_cancel.call_count, 2)
        second_status = json.loads((self.run_dir / "02-opencode-check-status.json").read_text(encoding="utf-8"))
        self.assertEqual(second_status["state"], "cancelled")


if __name__ == "__main__":
    unittest.main()
