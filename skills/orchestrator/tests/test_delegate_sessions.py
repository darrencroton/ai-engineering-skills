from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import delegate_sessions


class DelegateSessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write_rows(self, name: str, rows: list[dict]) -> Path:
        path = self.root / name
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return path

    def test_session_activity_uses_one_payload_shape_for_claude_and_codex(self):
        claude_path = self.write_rows(
            "claude.jsonl",
            [
                {
                    "type": "assistant",
                    "timestamp": "2026-07-13T00:00:00Z",
                    "message": {"content": [{"type": "tool_use", "name": "Read"}]},
                },
                {"type": "user", "timestamp": "2026-07-13T00:00:01Z", "message": {"content": []}},
            ],
        )
        session_id = "12345678-1234-1234-1234-123456789abc"
        codex_path = self.write_rows(
            f"rollout-{session_id}.jsonl",
            [
                {
                    "type": "response_item",
                    "timestamp": "2026-07-13T00:00:00Z",
                    "payload": {"type": "function_call", "name": "exec_command"},
                },
                {
                    "type": "response_item",
                    "timestamp": "2026-07-13T00:00:01Z",
                    "payload": {"type": "function_call_output"},
                },
            ],
        )

        claude = delegate_sessions.session_activity("claude", claude_path)
        codex = delegate_sessions.session_activity("codex", codex_path)

        common_keys = {
            "session_path",
            "session_mtime_at",
            "session_mtime_age_s",
            "session_size",
            "last_event_at",
            "last_event_type",
            "last_event_age_s",
            "last_assistant_at",
            "last_assistant_type",
            "last_assistant_detail",
            "last_assistant_age_s",
        }
        self.assertTrue(common_keys.issubset(claude))
        self.assertTrue(common_keys.issubset(codex))
        self.assertEqual(claude["last_event_type"], "user")
        self.assertEqual(claude["last_assistant_type"], "assistant.tool_use")
        self.assertEqual(claude["last_assistant_detail"], "Read")
        self.assertEqual(codex["last_event_type"], "tool.output")
        self.assertEqual(codex["last_assistant_type"], "assistant.function_call")
        self.assertEqual(codex["last_assistant_detail"], "exec_command")
        self.assertEqual(codex["session_id"], session_id)

    def test_unknown_tool_has_no_session_fallback(self):
        path = self.write_rows("unknown.jsonl", [])
        self.assertEqual(delegate_sessions.session_activity("other", path), {})
        self.assertIsNone(delegate_sessions.extract_session_text("other", path))

    def test_claude_activity_tracks_bare_assistant_row(self):
        path = self.write_rows(
            "claude-bare-assistant.jsonl",
            [{"type": "assistant", "timestamp": "2026-07-13T00:00:00Z", "message": {}}],
        )

        activity = delegate_sessions.session_activity("claude", path)

        self.assertEqual(activity["last_event_type"], "assistant")
        self.assertEqual(activity["last_assistant_type"], "assistant")
        self.assertNotIn("last_assistant_detail", activity)

    def test_extract_session_text_reads_latest_vendor_answer(self):
        claude_path = self.write_rows(
            "claude-answer.jsonl",
            [
                {"type": "assistant", "message": {"content": [{"type": "text", "text": "older"}]}},
                {"type": "assistant", "message": {"content": [{"type": "text", "text": "latest Claude"}]}},
            ],
        )
        codex_path = self.write_rows(
            "codex-answer.jsonl",
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "older"}],
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "latest Codex"}],
                    },
                },
            ],
        )

        self.assertEqual(delegate_sessions.extract_session_text("claude", claude_path), "latest Claude")
        self.assertEqual(delegate_sessions.extract_session_text("codex", codex_path), "latest Codex")

    def test_settable_session_ids_resolve_exact_transcript_paths(self):
        session_id = "12345678-1234-1234-1234-123456789abc"
        claude_path = self.root / "claude" / f"{session_id}.jsonl"
        copilot_path = self.root / "copilot" / session_id / "events.jsonl"
        claude_path.parent.mkdir()
        copilot_path.parent.mkdir(parents=True)
        claude_path.write_text("", encoding="utf-8")
        copilot_path.write_text("", encoding="utf-8")
        repo = self.root / "repo"
        repo.mkdir()

        with mock.patch.object(delegate_sessions, "claude_project_root", return_value=claude_path.parent):
            resolved_claude = delegate_sessions.resolve_launch_session(
                {
                    "tool": "claude",
                    "command": ["claude", "-p", "prompt", "--session-id", session_id, "--add-dir", str(repo)],
                }
            )
        with mock.patch.object(delegate_sessions, "copilot_session_root", return_value=self.root / "copilot"):
            resolved_copilot = delegate_sessions.resolve_launch_session(
                {
                    "tool": "copilot",
                    "command": ["copilot", "-p", "prompt", "--session-id", session_id, "--add-dir", str(repo)],
                }
            )

        self.assertEqual(resolved_claude, (session_id, claude_path))
        self.assertEqual(resolved_copilot, (session_id, copilot_path))

    def test_codex_resolution_rejects_newer_unrelated_prompt(self):
        repo = self.root / "repo"
        repo.mkdir()
        matching_id = "12345678-1234-1234-1234-123456789abc"
        unrelated_id = "87654321-4321-4321-4321-cba987654321"
        matching = self.write_rows(
            f"rollout-{matching_id}.jsonl",
            [
                {"type": "session_meta", "payload": {"cwd": str(repo)}},
                {"type": "event_msg", "payload": {"type": "user_message", "message": "owned prompt"}},
            ],
        )
        unrelated = self.write_rows(
            f"rollout-{unrelated_id}.jsonl",
            [
                {"type": "session_meta", "payload": {"cwd": str(repo)}},
                {"type": "event_msg", "payload": {"type": "user_message", "message": "other prompt"}},
            ],
        )
        unrelated.touch()
        started_at = datetime.fromtimestamp(time.time() - 1, timezone.utc).isoformat()
        entry = {
            "tool": "codex",
            "command": ["codex", "exec", "owned prompt", "-C", str(repo)],
            "outfile": str(self.root / "empty-output.txt"),
            "started_at": started_at,
        }

        with mock.patch.object(delegate_sessions, "codex_session_root", return_value=self.root):
            session_id, session_path = delegate_sessions.resolve_launch_session(entry)

        self.assertEqual(session_id, matching_id)
        self.assertEqual(session_path, matching)

    def test_codex_ambiguous_identical_sessions_are_null(self):
        repo = self.root / "repo"
        repo.mkdir()
        for session_id in (
            "12345678-1234-1234-1234-123456789abc",
            "87654321-4321-4321-4321-cba987654321",
        ):
            self.write_rows(
                f"rollout-{session_id}.jsonl",
                [
                    {"type": "session_meta", "payload": {"cwd": str(repo)}},
                    {"type": "event_msg", "payload": {"type": "user_message", "message": "same prompt"}},
                ],
            )
        entry = {
            "tool": "codex",
            "command": ["codex", "exec", "same prompt", "-C", str(repo)],
            "outfile": str(self.root / "empty-output.txt"),
            "started_at": datetime.fromtimestamp(time.time() - 1, timezone.utc).isoformat(),
        }

        with mock.patch.object(delegate_sessions, "codex_session_root", return_value=self.root):
            self.assertEqual(delegate_sessions.resolve_launch_session(entry), (None, None))

    def test_opencode_session_id_requires_prompt_cwd_and_start_time_match(self):
        database = self.root / "opencode.db"
        repo = self.root / "repo"
        repo.mkdir()
        repo = repo.resolve()
        connection = sqlite3.connect(database)
        connection.executescript(
            """
            CREATE TABLE session (id TEXT PRIMARY KEY, directory TEXT NOT NULL, time_created INTEGER NOT NULL);
            CREATE TABLE part (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, time_created INTEGER NOT NULL, data TEXT NOT NULL);
            """
        )
        started_epoch = time.time() - 1
        started_ms = int(started_epoch * 1000)
        connection.executemany(
            "INSERT INTO session (id, directory, time_created) VALUES (?, ?, ?)",
            [
                ("ses_owned", str(repo), started_ms + 1000),
                ("ses_unrelated", str(repo), started_ms + 20000),
            ],
        )
        connection.executemany(
            "INSERT INTO part (id, session_id, time_created, data) VALUES (?, ?, ?, ?)",
            [
                ("part_owned", "ses_owned", started_ms + 1001, json.dumps({"type": "text", "text": "owned prompt"})),
                ("part_other", "ses_unrelated", started_ms + 20001, json.dumps({"type": "text", "text": "owned prompt"})),
            ],
        )
        connection.commit()
        connection.close()
        entry = {
            "tool": "opencode",
            "command": ["opencode", "run", "owned prompt", "--dir", str(repo)],
            "cwd": str(repo),
            "started_at": datetime.fromtimestamp(started_epoch, timezone.utc).isoformat(),
        }

        with mock.patch.object(delegate_sessions, "opencode_session_db", return_value=database):
            session_id, session_path = delegate_sessions.resolve_launch_session(entry)

        self.assertEqual(session_id, "ses_owned")
        self.assertIsNone(session_path)

    def test_opencode_malformed_part_does_not_hide_matching_session(self):
        database = self.root / "opencode.db"
        repo = (self.root / "repo").resolve()
        repo.mkdir()
        connection = sqlite3.connect(database)
        connection.executescript(
            """
            CREATE TABLE session (id TEXT PRIMARY KEY, directory TEXT NOT NULL, time_created INTEGER NOT NULL);
            CREATE TABLE part (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, time_created INTEGER NOT NULL, data TEXT NOT NULL);
            """
        )
        started_epoch = time.time() - 1
        started_ms = int(started_epoch * 1000)
        connection.execute(
            "INSERT INTO session (id, directory, time_created) VALUES (?, ?, ?)",
            ("ses_owned", str(repo), started_ms + 1000),
        )
        connection.executemany(
            "INSERT INTO part (id, session_id, time_created, data) VALUES (?, ?, ?, ?)",
            [
                ("part_bad", "ses_owned", started_ms + 1001, "{not-json"),
                ("part_owned", "ses_owned", started_ms + 1002, json.dumps({"type": "text", "text": "owned prompt"})),
            ],
        )
        connection.commit()
        connection.close()
        entry = {
            "tool": "opencode",
            "command": ["opencode", "run", "owned prompt", "--dir", str(repo)],
            "cwd": str(repo),
            "started_at": datetime.fromtimestamp(started_epoch, timezone.utc).isoformat(),
        }

        with mock.patch.object(delegate_sessions, "opencode_session_db", return_value=database):
            self.assertEqual(delegate_sessions.resolve_launch_session(entry), ("ses_owned", None))

    def test_opencode_ambiguous_identical_sessions_are_null(self):
        database = self.root / "opencode.db"
        repo = (self.root / "repo").resolve()
        repo.mkdir()
        connection = sqlite3.connect(database)
        connection.executescript(
            """
            CREATE TABLE session (id TEXT PRIMARY KEY, directory TEXT NOT NULL, time_created INTEGER NOT NULL);
            CREATE TABLE part (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, time_created INTEGER NOT NULL, data TEXT NOT NULL);
            """
        )
        started_epoch = time.time() - 1
        started_ms = int(started_epoch * 1000)
        for index, session_id in enumerate(("ses_one", "ses_two"), start=1):
            connection.execute(
                "INSERT INTO session (id, directory, time_created) VALUES (?, ?, ?)",
                (session_id, str(repo), started_ms + index),
            )
            connection.execute(
                "INSERT INTO part (id, session_id, time_created, data) VALUES (?, ?, ?, ?)",
                (
                    f"part_{index}",
                    session_id,
                    started_ms + index,
                    json.dumps({"type": "text", "text": "same prompt"}),
                ),
            )
        connection.commit()
        connection.close()
        entry = {
            "tool": "opencode",
            "command": ["opencode", "run", "same prompt", "--dir", str(repo)],
            "cwd": str(repo),
            "started_at": datetime.fromtimestamp(started_epoch, timezone.utc).isoformat(),
        }

        with mock.patch.object(delegate_sessions, "opencode_session_db", return_value=database):
            self.assertEqual(delegate_sessions.resolve_launch_session(entry), (None, None))

    def test_qwen_resolution_rejects_newer_unrelated_session(self):
        repo = self.root / "repo"
        chats = self.root / "qwen-project" / "chats"
        repo.mkdir()
        repo = repo.resolve()
        chats.mkdir(parents=True)
        matching_id = "12345678-1234-1234-1234-123456789abc"
        unrelated_id = "87654321-4321-4321-4321-cba987654321"
        matching = chats / f"{matching_id}.jsonl"
        unrelated = chats / f"{unrelated_id}.jsonl"
        started_epoch = time.time() - 1
        matching.write_text(
            json.dumps(
                {
                    "sessionId": matching_id,
                    "timestamp": datetime.fromtimestamp(started_epoch + 0.1, timezone.utc).isoformat(),
                    "type": "user",
                    "cwd": str(repo),
                    "message": {"parts": [{"text": "owned prompt"}]},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        unrelated.write_text(
            json.dumps(
                {
                    "sessionId": unrelated_id,
                    "timestamp": datetime.fromtimestamp(started_epoch + 20, timezone.utc).isoformat(),
                    "type": "user",
                    "cwd": str(repo),
                    "message": {"parts": [{"text": "owned prompt"}]},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        entry = {
            "tool": "qwen",
            "command": ["qwen", "--prompt", "owned prompt"],
            "cwd": str(repo),
            "started_at": datetime.fromtimestamp(started_epoch, timezone.utc).isoformat(),
        }

        with mock.patch.object(delegate_sessions, "qwen_project_root", return_value=chats.parent):
            session_id, session_path = delegate_sessions.resolve_launch_session(entry)

        self.assertEqual(session_id, matching_id)
        self.assertEqual(session_path, matching)

    def test_qwen_ambiguous_identical_sessions_are_null(self):
        repo = (self.root / "repo").resolve()
        chats = self.root / "qwen-project" / "chats"
        repo.mkdir()
        chats.mkdir(parents=True)
        started_epoch = time.time() - 1
        for index, session_id in enumerate(
            (
                "12345678-1234-1234-1234-123456789abc",
                "87654321-4321-4321-4321-cba987654321",
            ),
            start=1,
        ):
            (chats / f"{session_id}.jsonl").write_text(
                json.dumps(
                    {
                        "sessionId": session_id,
                        "timestamp": datetime.fromtimestamp(started_epoch + index, timezone.utc).isoformat(),
                        "type": "user",
                        "cwd": str(repo),
                        "message": {"parts": [{"text": "same prompt"}]},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
        entry = {
            "tool": "qwen",
            "command": ["qwen", "--prompt", "same prompt"],
            "cwd": str(repo),
            "started_at": datetime.fromtimestamp(started_epoch, timezone.utc).isoformat(),
        }

        with mock.patch.object(delegate_sessions, "qwen_project_root", return_value=chats.parent):
            self.assertEqual(delegate_sessions.resolve_launch_session(entry), (None, None))

    def test_unprovable_post_launch_session_is_null(self):
        repo = self.root / "repo"
        repo.mkdir()
        entry = {
            "tool": "qwen",
            "command": ["qwen", "--prompt", "missing prompt"],
            "cwd": str(repo),
            "started_at": "2026-07-23T00:00:00Z",
        }

        with mock.patch.object(delegate_sessions, "qwen_project_root", return_value=self.root / "missing"):
            self.assertEqual(delegate_sessions.resolve_launch_session(entry), (None, None))


if __name__ == "__main__":
    unittest.main()
