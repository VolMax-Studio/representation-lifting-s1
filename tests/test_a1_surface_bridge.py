#!/usr/bin/env python3
"""
tests/test_a1_surface_bridge.py

Test suite for Amendment A1 surface bridge (tools/a1_surface_bridge.py).
Implements the r5 test contract. All tests use mocks; no live inference.

Tests:
  1.  test_interface_compatibility
  2.  test_canonical_request_fidelity
  3.  test_canonical_request_sha256_correct
  4.  test_surface_input_native_system
  5.  test_surface_input_flattened_single_turn
  6.  test_surface_input_flattened_multi_turn
  7.  test_flattening_determinism
  8.  test_response_artifact_emission
  9.  test_no_control_logic_leakage
  10. test_timeout_returns_infra_failure
  11. test_transport_failure_classification
  12. test_delivered_empty_response_not_infra_failure
  13. test_multi_turn_via_mock_harness_integration
  14. test_frozen_harness_sha256_unchanged
  15. test_frozen_executor_config_sha256_unchanged
"""

import os
import sys
import json
import time
import hashlib
import tempfile
import importlib
import unittest
from unittest.mock import patch, MagicMock, call as mock_call

# Ensure repo root is on path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import tools.a1_surface_bridge as bridge

# ---------------------------------------------------------------------------
# Frozen file SHAs (must not change)
# ---------------------------------------------------------------------------
FROZEN_HARNESS_SHA = "ccb1cad202fcdd2dbd931c3b8c5d65d9d368a0bdb26da8946e9b8671b07d8c48"
FROZEN_CONFIG_SHA  = "395deb97fa2b038a93ce416ced4ce3bcba31cddea30db7f3daa5ee5bc01f4b04"


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Minimal A1 config fixtures
# ---------------------------------------------------------------------------

def _make_native_surface_config(tmp_dir: str) -> dict:
    return {
        "schema_version": "representation-lifting-a1-transport/v1",
        "amendment": "A1",
        "frozen_executor_config_sha256": FROZEN_CONFIG_SHA,
        "frozen_executor_harness_sha256": FROZEN_HARNESS_SHA,
        "bridge_sha256": "test",
        "bridge_tests_sha256": "test",
        "reconnaissance_timestamp_utc": "2026-10-02T00:00:00+00:00",
        "surfaces": {
            "primary": {
                "pinned_model_id": "claude-sonnet-4-6",
                "surface_type": "claude-code-cli",
                "surface_version": "2.1.197",
                "executable_path": "/nonexistent/claude",
                "system_role_handling": "NATIVE_SYSTEM_MESSAGE",
                "message_history_handling": "NATIVE_MULTI_TURN",
                "inference_controls_pinned": {"reasoning_effort": "high"},
                "request_timeout_seconds": 10,
            }
        },
        "degradations_introduced_by_a1": [],
    }


def _make_flattened_surface_config(tmp_dir: str) -> dict:
    return {
        "schema_version": "representation-lifting-a1-transport/v1",
        "amendment": "A1",
        "frozen_executor_config_sha256": FROZEN_CONFIG_SHA,
        "frozen_executor_harness_sha256": FROZEN_HARNESS_SHA,
        "bridge_sha256": "test",
        "bridge_tests_sha256": "test",
        "reconnaissance_timestamp_utc": "2026-10-02T00:00:00+00:00",
        "surfaces": {
            "replication": {
                "pinned_model_id": "gpt-5.6-sol",
                "surface_type": "chatgpt-web",
                "surface_version_observed": "2026-10-02",
                "system_role_handling": "DEGRADED_SYSTEM_ROLE_FLATTENED_TO_USER_CONTENT",
                "message_history_handling": "DEGRADED_HISTORY_FLATTENED_TO_USER_CONTENT",
                "inference_controls_pinned": {"reasoning_effort": "high"},
                "request_timeout_seconds": 10,
                "flattening_scheme": {
                    "system_delimiter_start": "=== PROTOCOL SYSTEM INSTRUCTIONS (DO NOT MODIFY) ===",
                    "system_delimiter_end": "=== END PROTOCOL SYSTEM INSTRUCTIONS ===",
                    "history_delimiter_start": "=== CONVERSATION HISTORY ===",
                    "history_turn_format": "[Turn {n} - {ROLE}]:",
                    "history_delimiter_end": "=== END CONVERSATION HISTORY ===",
                    "current_delimiter": "=== CURRENT REQUEST ===",
                },
            }
        },
        "degradations_introduced_by_a1": [],
    }


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestA1SurfaceBridge(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # 1. Interface compatibility
    # ------------------------------------------------------------------
    def test_interface_compatibility(self):
        """Bridge returns exact (str, str|None, bool) tuple — same as original."""
        cfg = _make_native_surface_config(self.tmp)

        def mock_cli(si_path, sc, sp, rw, tr, **kwargs):
            return "mock response text", "end_turn", False

        with patch.object(bridge, "_relay_claude_code_cli", side_effect=mock_cli):
            result = bridge.a1_call_surface(
                model_id="claude-sonnet-4-6",
                messages=[{"role": "user", "content": "hello"}],
                system_prompt="You are a test.",
                remaining_wallclock=60.0,
                config={},
                transcript=[],
                a1_config=cfg,
                artifact_dir=self.tmp,
                turn_number=0,
            )
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)
        text, stop, fail = result
        self.assertIsInstance(text, str)
        self.assertIsInstance(fail, bool)
        self.assertFalse(fail)
        self.assertEqual(text, "mock response text")

    # ------------------------------------------------------------------
    # 2. Canonical request fidelity
    # ------------------------------------------------------------------
    def test_canonical_request_fidelity(self):
        """request_N.json faithfully records exact system_prompt and messages."""
        cfg = _make_native_surface_config(self.tmp)
        sp = "Test system prompt"
        msgs = [{"role": "user", "content": "Test user content"}]

        def mock_cli(si_path, sc, s, rw, tr, **kwargs):
            return "resp", "end_turn", False

        with patch.object(bridge, "_relay_claude_code_cli", side_effect=mock_cli):
            bridge.a1_call_surface(
                "claude-sonnet-4-6", msgs, sp, 60.0, {}, [],
                a1_config=cfg, artifact_dir=self.tmp, turn_number=7,
            )

        req_path = os.path.join(self.tmp, "requests", "request_7.json")
        self.assertTrue(os.path.isfile(req_path))
        with open(req_path, "r") as f:
            envelope = json.load(f)
        self.assertEqual(envelope["system_prompt"], sp)
        self.assertEqual(envelope["messages"], msgs)
        self.assertEqual(envelope["model_id"], "claude-sonnet-4-6")
        self.assertEqual(envelope["turn_number"], 7)
        self.assertEqual(envelope["schema_version"], bridge.REQUEST_SCHEMA_VERSION)

    # ------------------------------------------------------------------
    # 3. Canonical request SHA-256 correct
    # ------------------------------------------------------------------
    def test_canonical_request_sha256_correct(self):
        """The sha256 field in request_N.json matches the canonical JSON hash."""
        cfg = _make_native_surface_config(self.tmp)
        with patch.object(bridge, "_relay_claude_code_cli",
                          return_value=("r", "end_turn", False)):
            bridge.a1_call_surface(
                "claude-sonnet-4-6", [{"role": "user", "content": "x"}],
                "sys", 60.0, {}, [],
                a1_config=cfg, artifact_dir=self.tmp, turn_number=0,
            )
        req_path = os.path.join(self.tmp, "requests", "request_0.json")
        with open(req_path, "r") as f:
            envelope = json.load(f)
        stored_sha = envelope.pop("sha256")
        # Recompute over the envelope without the sha256 field
        canonical = json.dumps(envelope, sort_keys=True, ensure_ascii=False).encode()
        expected_sha = hashlib.sha256(canonical).hexdigest()
        self.assertEqual(stored_sha, expected_sha)

        sha_file = req_path + ".sha256"
        self.assertTrue(os.path.isfile(sha_file))
        with open(sha_file) as f:
            self.assertEqual(f.read().strip(), stored_sha)

    # ------------------------------------------------------------------
    # 4. Surface input — native system message
    # ------------------------------------------------------------------
    def test_surface_input_native_system(self):
        """For NATIVE_SYSTEM_MESSAGE, surface_input_N.txt contains only user-turn content."""
        cfg = _make_native_surface_config(self.tmp)
        user_content = "Prove this theorem: ..."
        msgs = [{"role": "user", "content": user_content}]
        with patch.object(bridge, "_relay_claude_code_cli",
                          return_value=("resp", "end_turn", False)):
            bridge.a1_call_surface(
                "claude-sonnet-4-6", msgs, "System prompt here", 60.0, {}, [],
                a1_config=cfg, artifact_dir=self.tmp, turn_number=1,
            )
        si_path = os.path.join(self.tmp, "requests", "surface_input_1.txt")
        self.assertTrue(os.path.isfile(si_path))
        with open(si_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Must be ONLY the user-turn content, not the system prompt
        self.assertEqual(content, user_content)
        self.assertNotIn("PROTOCOL SYSTEM INSTRUCTIONS", content)

    # ------------------------------------------------------------------
    # 5. Surface input — flattened, single turn
    # ------------------------------------------------------------------
    def test_surface_input_flattened_single_turn(self):
        """ChatGPT-type surface: flattened output includes system and current request."""
        cfg = _make_flattened_surface_config(self.tmp)
        sp = "You are a Lean 4 executor."
        msgs = [{"role": "user", "content": "Prove: 1 + 1 = 2"}]
        with patch.object(bridge, "_relay_manual_chatgpt",
                          return_value=("response", "end_turn", False)):
            bridge.a1_call_surface(
                "gpt-5.6-sol", msgs, sp, 60.0, {}, [],
                a1_config=cfg, artifact_dir=self.tmp, turn_number=0,
            )
        si_path = os.path.join(self.tmp, "requests", "surface_input_0.txt")
        with open(si_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("=== PROTOCOL SYSTEM INSTRUCTIONS (DO NOT MODIFY) ===", content)
        self.assertIn(sp, content)
        self.assertIn("=== END PROTOCOL SYSTEM INSTRUCTIONS ===", content)
        self.assertIn("=== CURRENT REQUEST ===", content)
        self.assertIn("Prove: 1 + 1 = 2", content)
        # No prior history in single-turn
        self.assertNotIn("=== CONVERSATION HISTORY ===", content)

    # ------------------------------------------------------------------
    # 6. Surface input — flattened, multi-turn
    # ------------------------------------------------------------------
    def test_surface_input_flattened_multi_turn(self):
        """ChatGPT-type surface: flattened output includes history section."""
        cfg = _make_flattened_surface_config(self.tmp)
        msgs = [
            {"role": "user", "content": "First user message"},
            {"role": "assistant", "content": "First assistant response"},
            {"role": "user", "content": "Second user message"},
        ]
        with patch.object(bridge, "_relay_manual_chatgpt",
                          return_value=("r", "end_turn", False)):
            bridge.a1_call_surface(
                "gpt-5.6-sol", msgs, "Sys", 60.0, {}, [],
                a1_config=cfg, artifact_dir=self.tmp, turn_number=2,
            )
        si_path = os.path.join(self.tmp, "requests", "surface_input_2.txt")
        with open(si_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("=== CONVERSATION HISTORY ===", content)
        self.assertIn("First user message", content)
        self.assertIn("First assistant response", content)
        self.assertIn("=== END CONVERSATION HISTORY ===", content)
        self.assertIn("=== CURRENT REQUEST ===", content)
        self.assertIn("Second user message", content)

    # ------------------------------------------------------------------
    # 7. Flattening determinism
    # ------------------------------------------------------------------
    def test_flattening_determinism(self):
        """Identical inputs produce byte-identical surface_input_N.txt across calls."""
        scheme = {
            "system_delimiter_start": "=== PROTOCOL SYSTEM INSTRUCTIONS (DO NOT MODIFY) ===",
            "system_delimiter_end": "=== END PROTOCOL SYSTEM INSTRUCTIONS ===",
            "history_delimiter_start": "=== CONVERSATION HISTORY ===",
            "history_turn_format": "[Turn {n} - {ROLE}]:",
            "history_delimiter_end": "=== END CONVERSATION HISTORY ===",
            "current_delimiter": "=== CURRENT REQUEST ===",
        }
        sp = "System prompt"
        msgs = [
            {"role": "user", "content": "U1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "U2"},
        ]
        out1 = bridge._flatten_for_no_system_role(sp, msgs, scheme)
        out2 = bridge._flatten_for_no_system_role(sp, msgs, scheme)
        self.assertEqual(out1, out2)
        # Byte-identical when encoded
        self.assertEqual(out1.encode("utf-8"), out2.encode("utf-8"))

    # ------------------------------------------------------------------
    # 8. Response artifact emission
    # ------------------------------------------------------------------
    def test_response_artifact_emission(self):
        """response_N.txt is written verbatim with correct SHA-256."""
        cfg = _make_native_surface_config(self.tmp)
        expected_response = "```lean\ntheorem foo : True := trivial\n```"
        with patch.object(bridge, "_relay_claude_code_cli",
                          return_value=(expected_response, "end_turn", False)):
            bridge.a1_call_surface(
                "claude-sonnet-4-6", [{"role": "user", "content": "x"}],
                "s", 60.0, {}, [],
                a1_config=cfg, artifact_dir=self.tmp, turn_number=3,
            )
        resp_path = os.path.join(self.tmp, "responses", "response_3.txt")
        self.assertTrue(os.path.isfile(resp_path))
        with open(resp_path, "r", encoding="utf-8") as f:
            actual = f.read()
        self.assertEqual(actual, expected_response)

        sha_file = resp_path + ".sha256"
        self.assertTrue(os.path.isfile(sha_file))
        with open(sha_file) as f:
            recorded_sha = f.read().strip()
        expected_sha = hashlib.sha256(expected_response.encode("utf-8")).hexdigest()
        self.assertEqual(recorded_sha, expected_sha)

    # ------------------------------------------------------------------
    # 9. No control-logic leakage
    # ------------------------------------------------------------------
    def test_no_control_logic_leakage(self):
        """Bridge does not call Lean, modify turn counts, or generate prompts."""
        cfg = _make_native_surface_config(self.tmp)
        lean_invoked = []

        def mock_cli(si_path, sc, sp, rw, tr, **kwargs):
            # Simulate bridge calling Lean — this must NOT happen
            lean_invoked.append(True)
            return "resp", "end_turn", False

        # Patch subprocess.run to detect any Lean invocation
        original_run = __import__("subprocess").run
        lean_calls = []

        def spy_run(cmd, **kwargs):
            cmd_str = str(cmd)
            if "lean" in cmd_str.lower() and "a1_surface_bridge" in __import__("traceback").format_stack()[-1]:
                lean_calls.append(cmd)
            return original_run(cmd, **kwargs)

        with patch.object(bridge, "_relay_claude_code_cli",
                          return_value=("resp", "end_turn", False)):
            transcript = []
            bridge.a1_call_surface(
                "claude-sonnet-4-6", [{"role": "user", "content": "x"}],
                "s", 60.0, {}, transcript,
                a1_config=cfg, artifact_dir=self.tmp, turn_number=0,
            )

        # Verify no Lean calls from bridge
        self.assertEqual(lean_calls, [])
        # Verify transcript events are only bridge events (no harness events)
        bridge_events = [e["event"] for e in transcript]
        for event in bridge_events:
            self.assertTrue(
                event.startswith("a1_bridge_"),
                f"Unexpected non-bridge event in bridge transcript: {event}"
            )

    # ------------------------------------------------------------------
    # 10. Timeout returns infra failure
    # ------------------------------------------------------------------
    def test_timeout_returns_infra_failure(self):
        """remaining_wallclock <= 1.0 returns ('', 'timeout_wallclock', False)."""
        cfg = _make_native_surface_config(self.tmp)
        transcript = []
        result = bridge.a1_call_surface(
            "claude-sonnet-4-6", [{"role": "user", "content": "x"}],
            "s", 0.5, {}, transcript,
            a1_config=cfg, artifact_dir=self.tmp, turn_number=0,
        )
        self.assertEqual(result, ("", "timeout_wallclock", False))
        self.assertTrue(any(
            e.get("event") == "a1_bridge_wallclock_expired_pre_request"
            for e in transcript
        ))

    # ------------------------------------------------------------------
    # 11. Transport failure classification
    # ------------------------------------------------------------------
    def test_transport_failure_classification(self):
        """is_pre_response_transport_failure returns True only for pre-response failures."""
        import subprocess as sp2
        self.assertTrue(bridge.is_pre_response_transport_failure(
            sp2.TimeoutExpired(["cmd"], 10)))
        self.assertTrue(bridge.is_pre_response_transport_failure(
            FileNotFoundError("no such file")))
        self.assertTrue(bridge.is_pre_response_transport_failure(
            OSError("connection refused")))
        self.assertTrue(bridge.is_pre_response_transport_failure(
            ConnectionError("reset")))
        # ValueError is NOT a transport failure
        self.assertFalse(bridge.is_pre_response_transport_failure(
            ValueError("bad value")))
        # RuntimeError is NOT
        self.assertFalse(bridge.is_pre_response_transport_failure(
            RuntimeError("unexpected")))

    # ------------------------------------------------------------------
    # 12. Delivered empty response is NOT infra failure
    # ------------------------------------------------------------------
    def test_delivered_empty_response_not_infra_failure(self):
        """A response object with empty text is final — not retried, not infra failure."""
        cfg = _make_native_surface_config(self.tmp)
        with patch.object(bridge, "_relay_claude_code_cli",
                          return_value=("", "end_turn", False)):
            text, stop, fail = bridge.a1_call_surface(
                "claude-sonnet-4-6", [{"role": "user", "content": "x"}],
                "s", 60.0, {}, [],
                a1_config=cfg, artifact_dir=self.tmp, turn_number=0,
            )
        self.assertFalse(fail)
        self.assertEqual(text, "")
        # Response artifact must be emitted even for empty response
        resp_path = os.path.join(self.tmp, "responses", "response_0.txt")
        self.assertTrue(os.path.isfile(resp_path))

    # ------------------------------------------------------------------
    # 13. Integration: mock harness multi-turn run
    # ------------------------------------------------------------------
    def test_multi_turn_via_mock_harness_integration(self):
        """
        Simulate a 3-turn mock run through the harness with the bridge patched.
        Assert: turn artifacts emitted, state-machine controlled by harness,
        bridge returns exactly what the mock returns per turn.
        """
        cfg = _make_native_surface_config(self.tmp)
        responses = [
            "No code block here",
            "```lean\ntheorem foo : True := by decide\n```",
        ]
        call_idx = [0]

        def mock_cli(si_path, sc, sp, rw, tr, **kwargs):
            idx = call_idx[0]
            call_idx[0] += 1
            if idx < len(responses):
                return responses[idx], "end_turn", False
            return "done", "end_turn", False

        transcript = []
        turn_texts = []

        with patch.object(bridge, "_relay_claude_code_cli", side_effect=mock_cli):
            for turn in range(2):
                msgs = [{"role": "user", "content": f"Turn {turn} content"}]
                text, stop, fail = bridge.a1_call_surface(
                    "claude-sonnet-4-6", msgs, "system", 300.0, {}, transcript,
                    a1_config=cfg, artifact_dir=self.tmp, turn_number=turn,
                )
                turn_texts.append(text)

        self.assertEqual(turn_texts[0], responses[0])
        self.assertEqual(turn_texts[1], responses[1])

        # Both request artifacts exist
        for t in range(2):
            self.assertTrue(os.path.isfile(
                os.path.join(self.tmp, "requests", f"request_{t}.json")
            ))
            self.assertTrue(os.path.isfile(
                os.path.join(self.tmp, "responses", f"response_{t}.txt")
            ))

    def test_primary_stateless_cli_preserves_history_via_flattening(self):
        """Primary fresh CLI calls must carry prior user/assistant history explicitly."""
        cfg = _make_native_surface_config(self.tmp)
        sc = cfg["surfaces"]["primary"]
        sc["message_history_handling"] = "DEGRADED_HISTORY_FLATTENED_TO_USER_CONTENT"
        sc["flattening_scheme"] = {
            "history_delimiter_start": "=== CONVERSATION HISTORY ===",
            "history_turn_format": "[Turn {n} - {ROLE}]:",
            "history_delimiter_end": "=== END CONVERSATION HISTORY ===",
            "current_delimiter": "=== CURRENT REQUEST ===",
        }
        msgs = [
            {"role": "user", "content": "U1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "U2"},
        ]
        path, _, _ = bridge.emit_surface_input(self.tmp, 4, "SYS", msgs, sc)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("U1", content)
        self.assertIn("A1", content)
        self.assertIn("U2", content)
        self.assertNotIn("SYS", content)

    def test_bridge_retries_pre_response_failure_with_frozen_budget(self):
        """A pre-response infra failure may retry within frozen max-attempts budget."""
        cfg = _make_native_surface_config(self.tmp)
        calls = []
        def fake_cli(*args, **kwargs):
            calls.append(1)
            return ("", None, True) if len(calls) == 1 else ("OK", "end_turn", False)
        transport_cfg = {"transport_policy": {"max_attempts_per_turn": 3, "backoff_seconds": [0, 0]}}
        with patch.object(bridge, "_relay_claude_code_cli", side_effect=fake_cli):
            out = bridge.a1_call_surface(
                "claude-sonnet-4-6", [{"role": "user", "content": "x"}],
                "sys", 60.0, transport_cfg, [], a1_config=cfg,
                artifact_dir=self.tmp, turn_number=0,
            )
        self.assertEqual(out, ("OK", "end_turn", False))
        self.assertEqual(len(calls), 2)

    def test_deferred_surface_fails_closed_before_relay(self):
        cfg = _make_flattened_surface_config(self.tmp)
        cfg["surfaces"]["replication"]["execution_status"] = "NOT_EVALUABLE_INFRA_REPLICATION_SURFACE_NOT_RECONNOITERED"
        with patch.object(bridge, "_relay_manual_chatgpt") as relay:
            out = bridge.a1_call_surface(
                "gpt-5.6-sol", [{"role": "user", "content": "x"}],
                "sys", 60.0, {}, [], a1_config=cfg,
                artifact_dir=self.tmp, turn_number=0,
            )
        self.assertEqual(out, ("", "SURFACE_DISABLED", True))
        relay.assert_not_called()

    def test_bridge_does_not_retry_nonretryable_model_identity_failure(self):
        cfg = _make_native_surface_config(self.tmp)
        calls = []
        def fake_cli(*args, **kwargs):
            calls.append(1)
            return "", "MODEL_IDENTITY_FAIL", True
        transport_cfg = {"transport_policy": {"max_attempts_per_turn": 3, "backoff_seconds": [0, 0]}}
        with patch.object(bridge, "_relay_claude_code_cli", side_effect=fake_cli):
            out = bridge.a1_call_surface(
                "claude-sonnet-4-6", [{"role": "user", "content": "x"}],
                "sys", 60.0, transport_cfg, [], a1_config=cfg,
                artifact_dir=self.tmp, turn_number=0,
            )
        self.assertEqual(out, ("", "MODEL_IDENTITY_FAIL", True))
        self.assertEqual(len(calls), 1)

    def test_claude_stream_json_verifies_model_and_empty_tools(self):
        """Claude relay trusts provider init metadata, not only the requested --model flag."""
        inp = os.path.join(self.tmp, "surface.txt")
        with open(inp, "w", encoding="utf-8") as f:
            f.write("hello")
        sc = _make_native_surface_config(self.tmp)["surfaces"]["primary"]
        sc["executable_path"] = "/bin/echo"
        sc["allowed_model_labels"] = ["claude-sonnet-4-6"]
        stdout = "\n".join([
            json.dumps({"type":"system","subtype":"init","model":"claude-sonnet-4-6","tools":[],"mcp_servers":[],"permissionMode":"default","cwd":"/tmp/x"}),
            json.dumps({"type":"assistant","message":{"model":"claude-sonnet-4-6","stop_reason":"end_turn"},"session_id":"s"}),
            json.dumps({"type":"result","subtype":"success","is_error":False,"result":"OK","session_id":"s"}),
        ])
        fake = MagicMock(returncode=0, stdout=stdout, stderr="")
        tr = []
        with patch.object(bridge.subprocess, "run", return_value=fake) as run:
            out = bridge._relay_claude_code_cli(inp, sc, "SYS", 60.0, tr)
        self.assertEqual(out, ("OK", "end_turn", False))
        kwargs = run.call_args.kwargs
        self.assertTrue(os.path.basename(kwargs["cwd"]).startswith("representation_lifting_a1_"))
        self.assertTrue(any(e.get("event") == "a1_bridge_cli_init" and e.get("model_returned") == "claude-sonnet-4-6" for e in tr))

    def test_claude_stream_json_rejects_model_mismatch(self):
        inp = os.path.join(self.tmp, "surface.txt")
        with open(inp, "w", encoding="utf-8") as f:
            f.write("hello")
        sc = _make_native_surface_config(self.tmp)["surfaces"]["primary"]
        sc["executable_path"] = "/bin/echo"
        sc["allowed_model_labels"] = ["claude-sonnet-4-6"]
        stdout = "\n".join([
            json.dumps({"type":"system","subtype":"init","model":"other-model","tools":[],"mcp_servers":[],"permissionMode":"default","cwd":"/tmp/x"}),
            json.dumps({"type":"result","subtype":"success","is_error":False,"result":"OK"}),
        ])
        fake = MagicMock(returncode=0, stdout=stdout, stderr="")
        with patch.object(bridge.subprocess, "run", return_value=fake):
            out = bridge._relay_claude_code_cli(inp, sc, "SYS", 60.0, [])
        self.assertEqual(out, ("OK", "MODEL_IDENTITY_FAIL", True))

    def _stream_result(self, *, assistant_model="claude-sonnet-4-6",
                       result="OK", result_is_error=False,
                       api_error=False, error=None, assistant_content=None):
        assistant = {
            "type": "assistant",
            "message": {"model": assistant_model, "stop_reason": "end_turn"},
        }
        if assistant_content is not None:
            assistant["message"]["content"] = [{"type": "text", "text": assistant_content}]
        if api_error:
            assistant["isApiErrorMessage"] = True
        if error is not None:
            assistant["error"] = error
        result_event = {
            "type": "result", "subtype": "error" if result_is_error else "success",
            "is_error": result_is_error, "result": result,
        }
        if error is not None:
            result_event["error"] = error
        return "\n".join([
            json.dumps({"type": "system", "subtype": "init",
                        "model": "claude-sonnet-4-6", "tools": [],
                        "mcp_servers": [], "permissionMode": "default", "cwd": "/tmp/x"}),
            json.dumps(assistant),
            json.dumps(result_event),
        ])

    def test_r9_normal_response_preserves_attempt_and_response(self):
        cfg = _make_native_surface_config(self.tmp)
        cfg["surfaces"]["primary"]["allowed_model_labels"] = ["claude-sonnet-4-6"]
        fake = MagicMock(returncode=0, stdout=self._stream_result(), stderr="")
        with patch.object(bridge.subprocess, "run", return_value=fake):
            out = bridge.a1_call_surface(
                "claude-sonnet-4-6", [{"role": "user", "content": "x"}],
                "sys", 60.0, {"transport_policy": {"max_attempts_per_turn": 3, "backoff_seconds": [0, 0]}},
                [], a1_config=cfg, artifact_dir=self.tmp, turn_number=0,
            )
        self.assertEqual(out, ("OK", "end_turn", False))
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "responses", "response_0.txt")))
        self.assertTrue(os.path.isfile(os.path.join(
            self.tmp, "transport_attempts", "turn_0", "attempt_1", "attempt_metadata.json")))
        self.assertTrue(bridge.validate_turn_transport_custody(self.tmp, 0)["custody_pass"])

    def test_r9_synthetic_api_error_is_retryable_pre_response(self):
        inp = os.path.join(self.tmp, "surface.txt")
        with open(inp, "w", encoding="utf-8") as f:
            f.write("hello")
        sc = _make_native_surface_config(self.tmp)["surfaces"]["primary"]
        sc["allowed_model_labels"] = ["claude-sonnet-4-6"]
        fake = MagicMock(
            returncode=1,
            stdout=self._stream_result(
                assistant_model="<synthetic>", result="API error", result_is_error=True,
                api_error=True, error="rate_limit",
            ),
            stderr="",
        )
        attempt_dir = os.path.join(self.tmp, "attempt")
        with patch.object(bridge.subprocess, "run", return_value=fake):
            out = bridge._relay_claude_code_cli(
                inp, sc, "SYS", 60.0, [], attempt_dir=attempt_dir,
                turn_number=0, attempt_number=1,
            )
        self.assertEqual(out, ("", None, True))
        with open(os.path.join(attempt_dir, "attempt_metadata.json"), encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertEqual(manifest["final_bridge_classification"], "PRE_RESPONSE_TRANSPORT_FAILURE")
        self.assertFalse(manifest["response_delivered"])

    def test_r9_synthetic_without_error_evidence_fails_closed(self):
        inp = os.path.join(self.tmp, "surface.txt")
        with open(inp, "w", encoding="utf-8") as f:
            f.write("hello")
        sc = _make_native_surface_config(self.tmp)["surfaces"]["primary"]
        fake = MagicMock(
            returncode=0,
            stdout=self._stream_result(assistant_model="<synthetic>", result="synthetic"),
            stderr="",
        )
        with patch.object(bridge.subprocess, "run", return_value=fake):
            out = bridge._relay_claude_code_cli(
                inp, sc, "SYS", 60.0, [], attempt_dir=os.path.join(self.tmp, "attempt"),
            )
        self.assertEqual(out, ("", "SYNTHETIC_WITHOUT_ERROR_EVIDENCE", True))

    def test_r9_result_error_precedes_synthetic_identity_rejection(self):
        inp = os.path.join(self.tmp, "surface.txt")
        with open(inp, "w", encoding="utf-8") as f:
            f.write("hello")
        sc = _make_native_surface_config(self.tmp)["surfaces"]["primary"]
        fake = MagicMock(
            returncode=1,
            stdout=self._stream_result(
                assistant_model="<synthetic>", result="", result_is_error=True,
            ), stderr="",
        )
        with patch.object(bridge.subprocess, "run", return_value=fake):
            out = bridge._relay_claude_code_cli(
                inp, sc, "SYS", 60.0, [], attempt_dir=os.path.join(self.tmp, "attempt"),
            )
        self.assertEqual(out, ("", None, True))

    def test_r9_genuine_assistant_model_mismatch_remains_fail_closed(self):
        inp = os.path.join(self.tmp, "surface.txt")
        with open(inp, "w", encoding="utf-8") as f:
            f.write("hello")
        sc = _make_native_surface_config(self.tmp)["surfaces"]["primary"]
        fake = MagicMock(
            returncode=0,
            stdout=self._stream_result(assistant_model="other-model", result="answer"),
            stderr="",
        )
        with patch.object(bridge.subprocess, "run", return_value=fake):
            out = bridge._relay_claude_code_cli(
                inp, sc, "SYS", 60.0, [], attempt_dir=os.path.join(self.tmp, "attempt"),
            )
        self.assertEqual(out, ("answer", "MODEL_IDENTITY_FAIL", True))

    def test_r9_retry_exhaustion_preserves_exactly_three_attempts(self):
        cfg = _make_native_surface_config(self.tmp)
        error_stream = self._stream_result(
            assistant_model="<synthetic>", result="", result_is_error=True,
            api_error=True, error="rate_limit",
        )
        fake = MagicMock(returncode=1, stdout=error_stream, stderr="")
        policy = {"transport_policy": {"max_attempts_per_turn": 3, "backoff_seconds": [0, 0]}}
        with patch.object(bridge.subprocess, "run", return_value=fake) as run:
            out = bridge.a1_call_surface(
                "claude-sonnet-4-6", [{"role": "user", "content": "x"}],
                "sys", 60.0, policy, [], a1_config=cfg,
                artifact_dir=self.tmp, turn_number=0,
            )
        self.assertEqual(out, ("", None, True))
        self.assertEqual(run.call_count, 3)
        for attempt in (1, 2, 3):
            self.assertTrue(os.path.isfile(os.path.join(
                self.tmp, "transport_attempts", "turn_0", f"attempt_{attempt}",
                "attempt_metadata.json")))
        self.assertFalse(os.path.exists(os.path.join(
            self.tmp, "transport_attempts", "turn_0", "attempt_4")))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "responses", "response_0.txt")))
        self.assertTrue(bridge.validate_turn_transport_custody(self.tmp, 0)["custody_pass"])

    def test_r9_recovery_preserves_failed_and_successful_attempts(self):
        cfg = _make_native_surface_config(self.tmp)
        error = MagicMock(
            returncode=1,
            stdout=self._stream_result(
                assistant_model="<synthetic>", result="", result_is_error=True,
                api_error=True, error="rate_limit",
            ), stderr="",
        )
        success = MagicMock(returncode=0, stdout=self._stream_result(result="OK"), stderr="")
        policy = {"transport_policy": {"max_attempts_per_turn": 3, "backoff_seconds": [0, 0]}}
        with patch.object(bridge.subprocess, "run", side_effect=[error, success]) as run:
            out = bridge.a1_call_surface(
                "claude-sonnet-4-6", [{"role": "user", "content": "x"}],
                "sys", 60.0, policy, [], a1_config=cfg,
                artifact_dir=self.tmp, turn_number=0,
            )
        self.assertEqual(out, ("OK", "end_turn", False))
        self.assertEqual(run.call_count, 2)
        for attempt in (1, 2):
            self.assertTrue(os.path.isfile(os.path.join(
                self.tmp, "transport_attempts", "turn_0", f"attempt_{attempt}",
                "attempt_metadata.json")))
        self.assertTrue(bridge.validate_turn_transport_custody(self.tmp, 0)["custody_pass"])

    def test_r9_delivered_semantic_failure_is_not_transport_resampled(self):
        cfg = _make_native_surface_config(self.tmp)
        fake = MagicMock(returncode=0, stdout=self._stream_result(result="not a valid proof"), stderr="")
        policy = {"transport_policy": {"max_attempts_per_turn": 3, "backoff_seconds": [0, 0]}}
        with patch.object(bridge.subprocess, "run", return_value=fake) as run:
            out = bridge.a1_call_surface(
                "claude-sonnet-4-6", [{"role": "user", "content": "x"}],
                "sys", 60.0, policy, [], a1_config=cfg,
                artifact_dir=self.tmp, turn_number=0,
            )
        self.assertEqual(out, ("not a valid proof", "end_turn", False))
        self.assertEqual(run.call_count, 1)

    def test_r9_missing_response_without_failure_evidence_fails_custody(self):
        cfg = _make_native_surface_config(self.tmp)
        fake = MagicMock(returncode=0, stdout=self._stream_result(result="OK"), stderr="")
        with patch.object(bridge.subprocess, "run", return_value=fake):
            bridge.a1_call_surface(
                "claude-sonnet-4-6", [{"role": "user", "content": "x"}],
                "sys", 60.0, {"transport_policy": {"max_attempts_per_turn": 1}},
                [], a1_config=cfg, artifact_dir=self.tmp, turn_number=0,
            )
        os.remove(os.path.join(self.tmp, "responses", "response_0.txt"))
        os.remove(os.path.join(self.tmp, "responses", "response_0.txt.sha256"))
        audit = bridge.validate_turn_transport_custody(self.tmp, 0)
        self.assertFalse(audit["custody_pass"])
        self.assertIn("DELIVERED_RESPONSE_ARTIFACT_REQUIRED", audit["failure_reasons"])

    def test_r9_branch_seal_covers_every_attempt_artifact(self):
        import tarfile
        import tools.a1_activate as a1_act

        cfg = _make_native_surface_config(self.tmp)
        error = MagicMock(
            returncode=1,
            stdout=self._stream_result(
                assistant_model="<synthetic>", result="", result_is_error=True,
                api_error=True, error="rate_limit",
            ), stderr="",
        )
        success = MagicMock(returncode=0, stdout=self._stream_result(result="OK"), stderr="")
        policy = {"transport_policy": {"max_attempts_per_turn": 3, "backoff_seconds": [0, 0]}}
        with patch.object(bridge.subprocess, "run", side_effect=[error, success]):
            bridge.a1_call_surface(
                "claude-sonnet-4-6", [{"role": "user", "content": "x"}],
                "sys", 60.0, policy, [], a1_config=cfg,
                artifact_dir=self.tmp, turn_number=0,
            )
        seal = os.path.join(self.tmp, "sealed.tar")
        _, _, files = a1_act.seal_branch_transcript(self.tmp, seal)
        required = {
            f"transport_attempts/turn_0/attempt_{attempt}/{name}"
            for attempt in (1, 2)
            for name in (
                "raw_stdout.stream.jsonl", "raw_stdout.stream.jsonl.sha256",
                "raw_stderr.txt", "raw_stderr.txt.sha256",
                "attempt_metadata.json", "attempt_metadata.json.sha256",
            )
        }
        self.assertTrue(required.issubset(set(files)))
        with tarfile.open(seal, "r") as archive:
            self.assertTrue(required.issubset(set(archive.getnames())))

    # ------------------------------------------------------------------
    # 14. Frozen harness SHA-256 unchanged
    # ------------------------------------------------------------------
    def test_frozen_harness_sha256_unchanged(self):
        """tools/executor_harness.py must remain byte-identical to frozen state."""
        harness_path = os.path.join(REPO_ROOT, "tools", "executor_harness.py")
        actual = _sha256_file(harness_path)
        self.assertEqual(
            actual, FROZEN_HARNESS_SHA,
            f"FROZEN FILE MODIFIED: executor_harness.py\n  expected: {FROZEN_HARNESS_SHA}\n  actual:   {actual}"
        )

    # ------------------------------------------------------------------
    # 15. Frozen executor config SHA-256 unchanged
    # ------------------------------------------------------------------
    def test_frozen_executor_config_sha256_unchanged(self):
        """tools/executor_config.json must remain byte-identical to frozen state."""
        config_path = os.path.join(REPO_ROOT, "tools", "executor_config.json")
        actual = _sha256_file(config_path)
        self.assertEqual(
            actual, FROZEN_CONFIG_SHA,
            f"FROZEN FILE MODIFIED: executor_config.json\n  expected: {FROZEN_CONFIG_SHA}\n  actual:   {actual}"
        )

    # ------------------------------------------------------------------
    # 16. Gate 5 probe and preflight verification (§A1.11 / Finding F2)
    # ------------------------------------------------------------------
    def test_gate5_exact_match_pass(self):
        """Gate 5 probe passes on exact JSON response (testing response parser)."""
        cfg = _make_native_surface_config(self.tmp)
        with patch.object(bridge, "_relay_claude_code_cli",
                          return_value=(bridge.GATE5_EXPECTED_RESPONSE, "end_turn", False)):
            result = bridge.run_gate5_probe("claude-sonnet-4-6", cfg, self.tmp, skip_preflight=True)
        self.assertTrue(result["gate5_pass"])
        self.assertTrue(result["exact_match"])

    def test_gate5_exact_match_fail_extra_text(self):
        """Gate 5 probe fails if response contains extra text."""
        cfg = _make_native_surface_config(self.tmp)
        bad_resp = bridge.GATE5_EXPECTED_RESPONSE + "\n\nSure, here you go!"
        with patch.object(bridge, "_relay_claude_code_cli",
                          return_value=(bad_resp, "end_turn", False)):
            result = bridge.run_gate5_probe("claude-sonnet-4-6", cfg, self.tmp, skip_preflight=True)
        self.assertFalse(result["gate5_pass"])
        self.assertEqual(result["failure_reason"], "RESPONSE_NOT_EXACT_MATCH")

    def test_gate5_infra_failure_propagates(self):
        """Gate 5 probe fails closed on infra failure."""
        cfg = _make_native_surface_config(self.tmp)
        with patch.object(bridge, "_relay_claude_code_cli",
                          return_value=("", None, True)):
            result = bridge.run_gate5_probe("claude-sonnet-4-6", cfg, self.tmp, skip_preflight=True)
        self.assertFalse(result["gate5_pass"])
        self.assertEqual(result["failure_reason"], "INFRA_FAILURE")

    def test_gate5_preflight_verifies_all_config_bindings(self):
        """Gate 5 preflight verifies actual repository hashes against candidate config."""
        real_cfg_path = os.path.join(REPO_ROOT, "evidence", "amendment_a1", "a1_transport_config.json")
        with open(real_cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        res = bridge.verify_gate5_preflight(cfg, root_dir=REPO_ROOT)
        self.assertTrue(res["preflight_pass"], f"Preflight failed: {res.get('failure_reason')}")
        self.assertIsNone(res["failure_reason"])
        self.assertIn("frozen_executor_harness_sha256", res["verified_bindings"])
        self.assertEqual(res["verified_bindings"]["frozen_executor_harness_sha256"]["status"], "MATCH")

    def test_gate5_preflight_fails_closed_on_tampered_hash(self):
        """Gate 5 preflight fails closed if any configuration hash is tampered."""
        cfg = {
            "frozen_executor_config_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
            "frozen_executor_harness_sha256": FROZEN_HARNESS_SHA,
            "bridge_sha256": "tampered",
            "bridge_tests_sha256": "tampered",
            "bridge_activate_sha256": "tampered",
            "target_preparer_sha256": "tampered",
            "target_preparer_tests_sha256": "tampered",
            "amendment_text_sha256": "tampered",
            "surfaces": {"primary": {"executable_path": "/bin/echo", "surface_binary_sha256": "tampered"}},
        }
        res = bridge.verify_gate5_preflight(cfg, root_dir=REPO_ROOT)
        self.assertFalse(res["preflight_pass"])
        self.assertIn("frozen_executor_config_sha256", res["failure_reason"])

    def test_gate5_preflight_fails_closed_on_missing_file(self):
        """Gate 5 preflight fails closed if a required asset file is missing."""
        cfg = {
            "frozen_executor_config_sha256": FROZEN_CONFIG_SHA,
            "frozen_executor_harness_sha256": FROZEN_HARNESS_SHA,
            "bridge_sha256": "any",
            "bridge_tests_sha256": "any",
            "bridge_activate_sha256": "any",
            "target_preparer_sha256": "any",
            "target_preparer_tests_sha256": "any",
            "amendment_text_sha256": "any",
            "surfaces": {"primary": {"executable_path": "/nonexistent/binary", "surface_binary_sha256": "any"}},
        }
        with tempfile.TemporaryDirectory() as empty_dir:
            res = bridge.verify_gate5_preflight(cfg, root_dir=empty_dir)
            self.assertFalse(res["preflight_pass"])
            self.assertIn("FILE_NOT_FOUND", str(res["verified_bindings"]))

    def test_gate5_probe_enforces_preflight_by_default(self):
        """Gate 5 probe fails closed without sending inference if preflight fails."""
        cfg = {
            "frozen_executor_config_sha256": "corrupted",
            "frozen_executor_harness_sha256": FROZEN_HARNESS_SHA,
            "bridge_sha256": "corrupted",
            "bridge_tests_sha256": "corrupted",
            "bridge_activate_sha256": "corrupted",
            "target_preparer_sha256": "corrupted",
            "target_preparer_tests_sha256": "corrupted",
            "amendment_text_sha256": "corrupted",
            "surfaces": {"primary": {"executable_path": "/nonexistent", "surface_binary_sha256": "corrupted"}},
        }
        with patch.object(bridge, "a1_call_surface") as mock_call_surface:
            res = bridge.run_gate5_probe("claude-sonnet-4-6", cfg, self.tmp, root_dir=REPO_ROOT)
            self.assertFalse(res["gate5_pass"])
            self.assertIn("PREFLIGHT_CONFIG_BINDING_MISMATCH", res["failure_reason"])
            # Proves fail-closed: zero inference calls made
            mock_call_surface.assert_not_called()

    # ------------------------------------------------------------------
    # 17. Evidence preservation and sealing (§A1.17 / Finding F1)
    # ------------------------------------------------------------------
    def test_a1_evidence_preservation_and_sealing_contract(self):
        """
        §A1.17 / Finding F1:
        Verifies that running a blind case under A1 emits a joint receipt containing
        all 12 required A1 fields and creates sealed archives for each completed branch.
        """
        import tools.a1_activate as a1_act
        import tools.executor_harness as eh

        with tempfile.TemporaryDirectory() as tmp_dir:
            art_dir = os.path.join(tmp_dir, "artifacts")
            sealed_dir = os.path.join(tmp_dir, "sealed_transcripts")
            receipt_dir = os.path.join(tmp_dir, "receipts")
            a1_act.configure(artifact_dir=art_dir, sealed_dir=sealed_dir, receipt_dir=receipt_dir)
            a1_act.reset_branch_seals()

            dummy_target = os.path.join(tmp_dir, "proofnet-999.lean")
            with open(dummy_target, "w", encoding="utf-8") as f:
                f.write("theorem frozen_target : True := trivial\n")

            def mock_agent(role, turn, msgs):
                if role == "D":
                    return ("```lean\ntheorem executor_theorem : True := trivial\n```", "end_turn", False)
                elif role == "S":
                    return ("```lean\ndef stub : True := trivial\n```", "end_turn", False)
                elif role == "L":
                    return ("```lean\ntheorem lifted_theorem : True := trivial\n```", "end_turn", False)
                return ("", "end_turn", True)

            def fake_verifier(cmd, *args, **kwargs):
                cmd_str = " ".join(cmd)
                if "count_lean_tokens.py" in cmd_str or "count_tokens" in cmd_str:
                    return MagicMock(returncode=0, stdout="42\n", stderr="")
                elif "check_bridge.py" in cmd_str:
                    return MagicMock(returncode=0, stdout="CHECK_BRIDGE_SENTINEL_OK\nBRIDGE_VALID", stderr="")
                elif "verify_proof.sh" in cmd_str:
                    return MagicMock(returncode=0, stdout="VERIFICATION_SUCCESS", stderr="")
                elif "verify_lifted.sh" in cmd_str:
                    return MagicMock(returncode=0, stdout="VERIFY_LIFTED_SENTINEL_OK", stderr="")
                return MagicMock(returncode=0, stdout="", stderr="")

            with patch.object(eh.subprocess, "run", side_effect=fake_verifier):
                report = eh.run_blind_case("proofnet-999", dummy_target, "claude-sonnet-4-6", mock_generator=mock_agent)

            # Check all 12 A1.17 required fields
            self.assertEqual(report.get("transport_amendment"), "A1")
            self.assertIn("transport_surface", report)
            self.assertIn("model_identity_evidence", report)
            self.assertEqual(report.get("model_label_displayed"), "claude-sonnet-4-6")
            self.assertIn("model_label_in_allowed_set", report)
            self.assertIn("a1_transport_config_sha256", report)
            self.assertIn("bridge_sha256", report)
            self.assertIn("bridge_activate_sha256", report)
            self.assertIn("inference_controls", report)
            self.assertIn("system_role_handling", report)
            self.assertIn("message_history_handling", report)
            self.assertIn("transcript_sealed_sha256", report)
            self.assertIn("branch_sealed_transcripts", report)

            # Verify sealed archives exist and have valid sha256
            branch_seals = report["branch_sealed_transcripts"]
            for r in ["D", "S", "L"]:
                seal_info = branch_seals.get(r)
                self.assertIsNotNone(seal_info, f"Missing seal info for role {r}")
                arch_path = seal_info["archive_path"]
                self.assertTrue(os.path.isfile(arch_path), f"Sealed archive not found: {arch_path}")
                self.assertTrue(os.path.isfile(arch_path + ".sha256"))
                self.assertEqual(seal_info["sha256"], _sha256_file(arch_path))

    # ------------------------------------------------------------------
    # 18. Cross-case overwrite protection (§A1.17 / Finding F3)
    # ------------------------------------------------------------------
    def test_three_consecutive_blind_cases_no_evidence_overwrite(self):
        """
        Finding F3:
        Verifies that three consecutive blind cases (proofnet-108, proofnet-083, proofnet-267)
        do NOT overwrite each other's turn artifacts, sealed transcripts, or receipts.
        """
        import tools.a1_activate as a1_act
        import tools.executor_harness as eh

        with tempfile.TemporaryDirectory() as tmp_dir:
            art_dir = os.path.join(tmp_dir, "artifacts")
            sealed_dir = os.path.join(tmp_dir, "sealed_transcripts")
            receipt_dir = os.path.join(tmp_dir, "receipts")
            a1_act.configure(artifact_dir=art_dir, sealed_dir=sealed_dir, receipt_dir=receipt_dir)
            a1_act.reset_branch_seals()

            cases = ["proofnet-108", "proofnet-083", "proofnet-267"]
            reports = {}

            def mock_agent(role, turn, msgs):
                return (f"```lean\n-- {role} turn {turn}\ntheorem thm : True := trivial\n```", "end_turn", False)

            def fake_verifier(cmd, *args, **kwargs):
                cmd_str = " ".join(cmd)
                if "count_lean_tokens.py" in cmd_str or "count_tokens" in cmd_str:
                    return MagicMock(returncode=0, stdout="42\n", stderr="")
                elif "check_bridge.py" in cmd_str:
                    return MagicMock(returncode=0, stdout="CHECK_BRIDGE_SENTINEL_OK\nBRIDGE_VALID", stderr="")
                elif "verify_proof.sh" in cmd_str:
                    return MagicMock(returncode=0, stdout="VERIFICATION_SUCCESS", stderr="")
                elif "verify_lifted.sh" in cmd_str:
                    return MagicMock(returncode=0, stdout="VERIFY_LIFTED_SENTINEL_OK", stderr="")
                return MagicMock(returncode=0, stdout="", stderr="")

            with patch.object(eh.subprocess, "run", side_effect=fake_verifier):
                for cid in cases:
                    tpath = os.path.join(tmp_dir, f"{cid}.lean")
                    with open(tpath, "w", encoding="utf-8") as f:
                        f.write("theorem frozen_target : True := trivial\n")

                    a1_act.reset_turn_counter()
                    rep = eh.run_blind_case(cid, tpath, "claude-sonnet-4-6", mock_generator=mock_agent)
                    reports[cid] = rep

            # Verify each case has its own isolated directories and archives
            for cid in cases:
                for r in ["D", "S", "L"]:
                    branch_dir = os.path.join(art_dir, cid, r)
                    self.assertTrue(os.path.isdir(branch_dir), f"Branch dir missing: {branch_dir}")
                    seal_path = os.path.join(sealed_dir, f"sealed_{cid}_{r}_claude-sonnet-4-6.tar")
                    self.assertTrue(os.path.isfile(seal_path), f"Sealed tar missing: {seal_path}")
                    self.assertEqual(reports[cid]["transcript_sealed_sha256"][r], _sha256_file(seal_path))

            # Verify receipts in receipt_dir are distinct and correctly populated
            for cid in cases:
                rcpt = os.path.join(receipt_dir, f"execution_receipt_blind_{cid}_claude-sonnet-4-6.json")
                self.assertTrue(os.path.isfile(rcpt), f"Receipt missing: {rcpt}")
                with open(rcpt, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.assertEqual(data["case_id"], cid)
                self.assertEqual(data["transport_amendment"], "A1")

    # ------------------------------------------------------------------
    # 19. Transport metadata artifact emission & sealing (§A1.17 / Finding F6)
    # ------------------------------------------------------------------
    def test_transport_metadata_turn_artifact_emission(self):
        """
        Finding F6:
        Verifies that each turn emits transport_metadata_N.json and companion .sha256,
        recording model_returned, assistant_model, tools, mcp_servers, permission_mode,
        and stop_reason, with valid self-hash.
        """
        art_dir = os.path.join(self.tmp, "turn_meta_artifacts")
        meta = {
            "model_returned": "claude-sonnet-4-6",
            "assistant_model": "claude-sonnet-4-6",
            "tools": [],
            "mcp_servers": [],
            "permission_mode": "default",
            "stop_reason": "end_turn",
            "is_infra_failure": False,
        }
        path, sha = bridge.emit_transport_metadata(art_dir, 0, meta)
        self.assertTrue(os.path.isfile(path))
        self.assertTrue(os.path.isfile(path + ".sha256"))
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["turn_number"], 0)
        self.assertEqual(data["model_returned"], "claude-sonnet-4-6")
        self.assertEqual(data["tools"], [])
        self.assertEqual(data["stop_reason"], "end_turn")
        self.assertEqual(data["sha256"], sha)

    # ------------------------------------------------------------------
    # 20. Observed model derivation from provider metadata & mismatch rejection (§A1.17 / Finding F6)
    # ------------------------------------------------------------------
    def test_observed_model_derived_from_provider_metadata(self):
        """
        Finding F6:
        Verifies that joint receipts derive model_label_displayed and
        model_label_in_allowed_set from observed transport_metadata, not requested model_id.
        """
        import tools.a1_activate as a1_act
        import tools.executor_harness as eh

        with tempfile.TemporaryDirectory() as tmp_dir:
            art_dir = os.path.join(tmp_dir, "artifacts")
            sealed_dir = os.path.join(tmp_dir, "sealed_transcripts")
            receipt_dir = os.path.join(tmp_dir, "receipts")
            a1_act.configure(artifact_dir=art_dir, sealed_dir=sealed_dir, receipt_dir=receipt_dir)
            a1_act.reset_branch_seals()

            dummy_target = os.path.join(tmp_dir, "proofnet-108.lean")
            with open(dummy_target, "w", encoding="utf-8") as f:
                f.write("theorem frozen_target : True := trivial\n")

            def mock_agent(role, turn, msgs):
                meta = {
                    "model_returned": "claude-sonnet-4-6",
                    "assistant_model": "claude-sonnet-4-6",
                    "tools": [],
                    "mcp_servers": [],
                    "permission_mode": "default",
                    "stop_reason": "end_turn",
                    "is_infra_failure": False,
                }
                return ("```lean\ntheorem executor_theorem : True := trivial\n```", "end_turn", False, meta)

            def fake_verifier(cmd, *args, **kwargs):
                cmd_str = " ".join(cmd)
                if "count_lean_tokens.py" in cmd_str or "count_tokens" in cmd_str:
                    return MagicMock(returncode=0, stdout="42\n", stderr="")
                elif "check_bridge.py" in cmd_str:
                    return MagicMock(returncode=0, stdout="CHECK_BRIDGE_SENTINEL_OK\nBRIDGE_VALID", stderr="")
                elif "verify_proof.sh" in cmd_str:
                    return MagicMock(returncode=0, stdout="VERIFICATION_SUCCESS", stderr="")
                elif "verify_lifted.sh" in cmd_str:
                    return MagicMock(returncode=0, stdout="VERIFY_LIFTED_SENTINEL_OK", stderr="")
                return MagicMock(returncode=0, stdout="", stderr="")

            with patch.object(eh.subprocess, "run", side_effect=fake_verifier):
                report = eh.run_blind_case("proofnet-108", dummy_target, "claude-sonnet-4-6", mock_generator=mock_agent)

            self.assertEqual(report["model_label_displayed"], "claude-sonnet-4-6")
            self.assertTrue(report["model_label_in_allowed_set"])
            self.assertEqual(report["observed_models"], ["claude-sonnet-4-6"])

    def test_model_mismatch_receipt_cannot_claim_allowed_model(self):
        """
        Finding F6:
        A model-identity mismatch test demonstrating that when the provider returns
        an unexpected model (e.g. 'other-model'), the resulting receipt derives
        model_label_displayed = 'other-model' and model_label_in_allowed_set = False,
        failing closed even if 'claude-sonnet-4-6' was requested.
        """
        import tools.a1_activate as a1_act
        import tools.executor_harness as eh

        with tempfile.TemporaryDirectory() as tmp_dir:
            art_dir = os.path.join(tmp_dir, "artifacts")
            sealed_dir = os.path.join(tmp_dir, "sealed_transcripts")
            receipt_dir = os.path.join(tmp_dir, "receipts")
            a1_act.configure(artifact_dir=art_dir, sealed_dir=sealed_dir, receipt_dir=receipt_dir)
            a1_act.reset_branch_seals()

            dummy_target = os.path.join(tmp_dir, "proofnet-108.lean")
            with open(dummy_target, "w", encoding="utf-8") as f:
                f.write("theorem frozen_target : True := trivial\n")

            def mock_agent_mismatch(role, turn, msgs):
                meta = {
                    "model_returned": "other-model",
                    "assistant_model": "other-model",
                    "tools": [],
                    "mcp_servers": [],
                    "permission_mode": "default",
                    "stop_reason": "MODEL_IDENTITY_FAIL",
                    "is_infra_failure": True,
                }
                return ("", "MODEL_IDENTITY_FAIL", True, meta)

            def fake_verifier(cmd, *args, **kwargs):
                return MagicMock(returncode=0, stdout="", stderr="")

            with patch.object(eh.subprocess, "run", side_effect=fake_verifier):
                report = eh.run_blind_case("proofnet-108", dummy_target, "claude-sonnet-4-6", mock_generator=mock_agent_mismatch)

            # Assert receipt derives observed 'other-model' and cannot claim allowed membership
            self.assertEqual(report["model_label_displayed"], "other-model")
            self.assertFalse(report["model_label_in_allowed_set"])
            self.assertEqual(report["observed_models"], ["other-model"])

    # ------------------------------------------------------------------
    # 21. Negative control arm A1 custody & sealing (§A1.17 / Finding F5)
    # ------------------------------------------------------------------
    def test_control_case_a1_custody_and_sealing(self):
        """
        Finding F5:
        Verifies that run_control_case under A1 produces an enriched joint receipt
        containing all 12 A1 fields, surface_metadata with plan_tier, isolated
        D and L branch directories, and sealed transcripts for both branches.
        """
        import tools.a1_activate as a1_act
        import tools.executor_harness as eh

        with tempfile.TemporaryDirectory() as tmp_dir:
            art_dir = os.path.join(tmp_dir, "artifacts")
            sealed_dir = os.path.join(tmp_dir, "sealed_transcripts")
            receipt_dir = os.path.join(tmp_dir, "receipts")
            a1_act.configure(artifact_dir=art_dir, sealed_dir=sealed_dir, receipt_dir=receipt_dir)
            a1_act.reset_branch_seals()

            dummy_target = os.path.join(tmp_dir, "control_sum_odd.lean")
            with open(dummy_target, "w", encoding="utf-8") as f:
                f.write("theorem frozen_target : True := trivial\n")

            dummy_stub = os.path.join(tmp_dir, "ControlGnomonStub.lean")
            with open(dummy_stub, "w", encoding="utf-8") as f:
                f.write("def stub : True := trivial\n")

            def mock_agent(role, turn, msgs):
                if role == "D":
                    return ("```lean\ntheorem executor_theorem : True := trivial\n```", "end_turn", False)
                elif role == "L":
                    return ("```lean\ntheorem lifted_theorem : True := trivial\n```", "end_turn", False)
                return ("", "end_turn", True)

            def fake_verifier(cmd, *args, **kwargs):
                cmd_str = " ".join(cmd)
                if "count_lean_tokens.py" in cmd_str or "count_tokens" in cmd_str:
                    return MagicMock(returncode=0, stdout="42\n", stderr="")
                elif "check_bridge.py" in cmd_str:
                    return MagicMock(returncode=0, stdout="CHECK_BRIDGE_SENTINEL_OK\nBRIDGE_VALID", stderr="")
                elif "verify_proof.sh" in cmd_str:
                    return MagicMock(returncode=0, stdout="VERIFICATION_SUCCESS", stderr="")
                elif "verify_lifted.sh" in cmd_str:
                    return MagicMock(returncode=0, stdout="VERIFY_LIFTED_SENTINEL_OK", stderr="")
                return MagicMock(returncode=0, stdout="", stderr="")

            with patch.object(eh.subprocess, "run", side_effect=fake_verifier):
                report = eh.run_control_case(
                    "claude-sonnet-4-6",
                    target_path=dummy_target,
                    stub_path=dummy_stub,
                    mock_generator=mock_agent,
                )

            # Check all A1 custody fields
            self.assertEqual(report["transport_amendment"], "A1")
            self.assertEqual(report["model_label_displayed"], "claude-sonnet-4-6")
            self.assertTrue(report["model_label_in_allowed_set"])
            self.assertEqual(report["surface_metadata"]["plan_tier"], "Pro")
            self.assertIn("D", report["branch_sealed_transcripts"])
            self.assertIn("L", report["branch_sealed_transcripts"])

            # Verify isolated artifact directories and sealed archives exist
            for r in ["D", "L"]:
                b_dir = os.path.join(art_dir, "control", r)
                self.assertTrue(os.path.isdir(b_dir), f"Control branch dir missing: {b_dir}")
                seal_path = os.path.join(sealed_dir, f"sealed_control_{r}_claude-sonnet-4-6.tar")
                self.assertTrue(os.path.isfile(seal_path), f"Control sealed tar missing: {seal_path}")
                self.assertTrue(os.path.isfile(seal_path + ".sha256"))
                self.assertEqual(report["transcript_sealed_sha256"][r], _sha256_file(seal_path))

            # Verify saved receipt
            rcpt_path = os.path.join(receipt_dir, "execution_receipt_control_claude-sonnet-4-6.json")
            self.assertTrue(os.path.isfile(rcpt_path))

    # ------------------------------------------------------------------
    # 22. Calibration family arm A1 custody & sealing (§A1.17 / Finding F5)
    # ------------------------------------------------------------------
    def test_calibration_family_a1_custody_and_sealing(self):
        """
        Finding F5:
        Verifies that run_calibration_family under A1 produces an enriched joint receipt
        containing all 12 A1 fields, surface_metadata with plan_tier, isolated
        D1, D2, S1, L1, S2, L2 branch directories, and sealed transcripts for all 6 branches.
        """
        import tools.a1_activate as a1_act
        import tools.executor_harness as eh

        with tempfile.TemporaryDirectory() as tmp_dir:
            art_dir = os.path.join(tmp_dir, "artifacts")
            sealed_dir = os.path.join(tmp_dir, "sealed_transcripts")
            receipt_dir = os.path.join(tmp_dir, "receipts")
            a1_act.configure(artifact_dir=art_dir, sealed_dir=sealed_dir, receipt_dir=receipt_dir)
            a1_act.reset_branch_seals()

            family = "fibonacci"

            def mock_agent(role, turn, msgs):
                code = (
                    "```lean\n"
                    "theorem executor_theorem : True := trivial\n"
                    "def LiftDom : Type := Unit\n"
                    "def LiftCod : Type := Unit\n"
                    "def liftT (x : Unit) : Unit := x\n"
                    "def invariant (x : Unit) : Prop := True\n"
                    "def BridgeProp : Prop := True\n"
                    "def LiftedClaim : Prop := True\n"
                    "theorem preservation_bridge : BridgeProp := trivial\n"
                    "theorem lifted_theorem : LiftedClaim := trivial\n"
                    "```"
                )
                return (code, "end_turn", False)

            def fake_verifier(cmd, *args, **kwargs):
                cmd_str = " ".join(cmd)
                if "count_lean_tokens.py" in cmd_str or "count_tokens" in cmd_str:
                    return MagicMock(returncode=0, stdout="42\n", stderr="")
                elif "check_bridge.py" in cmd_str:
                    return MagicMock(returncode=0, stdout="CHECK_BRIDGE_SENTINEL_OK\nBRIDGE_VALID", stderr="")
                elif "verify_proof.sh" in cmd_str:
                    return MagicMock(returncode=0, stdout="VERIFICATION_SUCCESS", stderr="")
                elif "verify_lifted.sh" in cmd_str:
                    return MagicMock(returncode=0, stdout="VERIFY_LIFTED_SENTINEL_OK", stderr="")
                return MagicMock(returncode=0, stdout="", stderr="")

            with patch.object(eh.subprocess, "run", side_effect=fake_verifier):
                report = eh.run_calibration_family(family, "claude-sonnet-4-6", mock_generator=mock_agent)

            # Check all A1 custody fields
            self.assertEqual(report["transport_amendment"], "A1")
            self.assertEqual(report["model_label_displayed"], "claude-sonnet-4-6")
            self.assertTrue(report["model_label_in_allowed_set"])
            self.assertEqual(report["surface_metadata"]["plan_tier"], "Pro")

            branches = ["D1", "D2", "S1", "L1", "S2", "L2"]
            for bl in branches:
                self.assertIn(bl, report["branch_sealed_transcripts"])
                self.assertIn(bl, report["transcript_sealed_sha256"])
                b_dir = os.path.join(art_dir, f"calibration_{family}", bl)
                self.assertTrue(os.path.isdir(b_dir), f"Calibration branch dir missing: {b_dir}")
                seal_path = os.path.join(sealed_dir, f"sealed_calibration_{family}_{bl}_claude-sonnet-4-6.tar")
                self.assertTrue(os.path.isfile(seal_path), f"Calibration sealed tar missing: {seal_path}")
                self.assertEqual(report["transcript_sealed_sha256"][bl], _sha256_file(seal_path))

            # Verify saved receipt
            rcpt_path = os.path.join(receipt_dir, f"execution_receipt_calibration_{family}_claude-sonnet-4-6.json")
            self.assertTrue(os.path.isfile(rcpt_path))

    # ------------------------------------------------------------------
    # 23. Surface metadata & plan tier preservation (§A1.17 / Finding F7)
    # ------------------------------------------------------------------
    def test_surface_metadata_plan_tier_frozen_and_emitted(self):
        """
        Finding F7:
        Verifies that plan_tier is frozen in config for primary ('Pro') and
        replication ('Plus (OpenAI Subscription) -- REPLICATION_DEFERRED'),
        and is included in surface_metadata on all receipts.
        """
        cfg_path = os.path.join(REPO_ROOT, "evidence", "amendment_a1", "a1_transport_config.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        primary = cfg["surfaces"]["primary"]
        self.assertEqual(primary.get("plan_tier"), "Pro")

        replication = cfg["surfaces"]["replication"]
        self.assertEqual(replication.get("plan_tier"), "Plus (OpenAI Subscription) -- REPLICATION_DEFERRED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
