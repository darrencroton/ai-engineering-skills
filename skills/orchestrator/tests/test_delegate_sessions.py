from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
