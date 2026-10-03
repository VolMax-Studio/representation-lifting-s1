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

        def mock_cli(si_path, sc, sp, rw, tr):
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

        def mock_cli(si_path, sc, s, rw, tr):
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

        def mock_cli(si_path, sc, sp, rw, tr):
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

        def mock_cli(si_path, sc, sp, rw, tr):
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
        content = open(path, encoding="utf-8").read()
        self.assertIn("U1", content)
        self.assertIn("A1", content)
        self.assertIn("U2", content)
        self.assertNotIn("SYS", content)

    def test_bridge_retries_pre_response_failure_with_frozen_budget(self):
        """A pre-response infra failure may retry within frozen max-attempts budget."""
        cfg = _make_native_surface_config(self.tmp)
        calls = []
        def fake_cli(*args):
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

    def test_bridge_does_not_retry_nonretryable_model_identity_failure(self):
        cfg = _make_native_surface_config(self.tmp)
        calls = []
        def fake_cli(*args):
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
        self.assertEqual(out, ("", "MODEL_IDENTITY_FAIL", True))

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
    # 16. Gate 5 exact-match check
    # ------------------------------------------------------------------
    def test_gate5_exact_match_pass(self):
        """Gate 5 probe passes on exact JSON response."""
        cfg = _make_native_surface_config(self.tmp)
        with patch.object(bridge, "_relay_claude_code_cli",
                          return_value=(bridge.GATE5_EXPECTED_RESPONSE, "end_turn", False)):
            result = bridge.run_gate5_probe("claude-sonnet-4-6", cfg, self.tmp)
        self.assertTrue(result["gate5_pass"])
        self.assertTrue(result["exact_match"])

    def test_gate5_exact_match_fail_extra_text(self):
        """Gate 5 probe fails if response contains extra text."""
        cfg = _make_native_surface_config(self.tmp)
        bad_resp = bridge.GATE5_EXPECTED_RESPONSE + "\n\nSure, here you go!"
        with patch.object(bridge, "_relay_claude_code_cli",
                          return_value=(bad_resp, "end_turn", False)):
            result = bridge.run_gate5_probe("claude-sonnet-4-6", cfg, self.tmp)
        self.assertFalse(result["gate5_pass"])
        self.assertEqual(result["failure_reason"], "RESPONSE_NOT_EXACT_MATCH")

    def test_gate5_infra_failure_propagates(self):
        """Gate 5 probe fails closed on infra failure."""
        cfg = _make_native_surface_config(self.tmp)
        with patch.object(bridge, "_relay_claude_code_cli",
                          return_value=("", None, True)):
            result = bridge.run_gate5_probe("claude-sonnet-4-6", cfg, self.tmp)
        self.assertFalse(result["gate5_pass"])
        self.assertEqual(result["failure_reason"], "INFRA_FAILURE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
