#!/usr/bin/env python3

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import a1_infra_recovery_01 as recovery
from tools import a1_surface_bridge as bridge


FROZEN_EXECUTOR_CONFIG_SHA = "395deb97fa2b038a93ce416ced4ce3bcba31cddea30db7f3daa5ee5bc01f4b04"
FROZEN_EXECUTOR_HARNESS_SHA = "ccb1cad202fcdd2dbd931c3b8c5d65d9d368a0bdb26da8946e9b8671b07d8c48"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def a1_config(tmp: str) -> dict:
    return {
        "surfaces": {
            "primary": {
                "pinned_model_id": "claude-sonnet-4-6",
                "surface_type": "claude-code-cli",
                "executable_path": "/bin/echo",
                "allowed_model_labels": ["claude-sonnet-4-6"],
                "system_role_handling": "NATIVE_SYSTEM_MESSAGE",
                "inference_controls_pinned": {"reasoning_effort": "high"},
                "request_timeout_seconds": 600,
            }
        }
    }


def stream_result(*, model="claude-sonnet-4-6", result=None, synthetic_error=False):
    init = {
        "type": "system", "subtype": "init", "model": "claude-sonnet-4-6",
        "tools": [], "mcp_servers": [], "permissionMode": "default",
    }
    if synthetic_error:
        assistant = {
            "type": "assistant", "isApiErrorMessage": True, "error": "rate_limit",
            "message": {"model": "<synthetic>", "stop_reason": None},
        }
        final = {
            "type": "result", "subtype": "success", "is_error": True,
            "result": "", "error": "rate_limit",
        }
    else:
        assistant = {
            "type": "assistant",
            "message": {"model": model, "stop_reason": "end_turn", "content": []},
        }
        final = {
            "type": "result", "subtype": "success", "is_error": False,
            "result": "" if result is None else result,
        }
    return "\n".join(json.dumps(event) for event in (init, assistant, final))


class TestInfraRecovery01(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.artifact_dir = Path(self.tmp.name) / "gate5"
        self.executor_config = json.loads(
            (REPO_ROOT / "tools" / "executor_config.json").read_text()
        )
        self.preflight = {
            "preflight_pass": True, "failure_reason": None, "verified_bindings": {}
        }

    def tearDown(self):
        self.tmp.cleanup()

    def run_probe(self, side_effect):
        with patch.object(bridge, "verify_gate5_preflight", return_value=self.preflight), \
             patch.object(bridge.time, "sleep"), \
             patch.object(bridge.subprocess, "run", side_effect=side_effect) as run:
            result = recovery.run_recovery_probe(
                a1_config(self.tmp.name), self.executor_config,
                self.artifact_dir, REPO_ROOT,
            )
        return result, run

    def test_gate5_receives_frozen_executor_transport_policy(self):
        cfg = a1_config(self.tmp.name)
        with patch.object(bridge, "run_gate5_probe", return_value={"gate5_pass": False}) as probe:
            recovery.run_recovery_probe(cfg, self.executor_config, self.artifact_dir, REPO_ROOT)
        self.assertIs(probe.call_args.kwargs["config"], self.executor_config)
        self.assertEqual(
            probe.call_args.kwargs["config"]["transport_policy"],
            {"max_attempts_per_turn": 3,
             "retryable_http_codes": [408, 429, 500, 502, 503, 504],
             "backoff_seconds": [5, 15], "request_timeout_seconds": 600},
        )

    def test_recovery_config_loads_bound_runtime_and_preserved_failure(self):
        cfg = json.loads((
            REPO_ROOT / "evidence" / "amendment_a1" / "INFRA_RECOVERY_01_CONFIG.json"
        ).read_text())
        recovery.verify_preserved_failed_gate5(REPO_ROOT, cfg)
        _, executor_config = recovery.load_bound_runtime(REPO_ROOT, cfg)
        self.assertEqual(
            executor_config["transport_policy"], self.executor_config["transport_policy"]
        )

    def test_modified_signed_tree_files_halt_before_namespace_or_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = [
                recovery.RECOVERY_CONFIG_RELATIVE_PATH,
                "tools/a1_infra_recovery_01.py",
                "tests/test_a1_infra_recovery_01.py",
                "INFRA_RECOVERY_01.md",
                "evidence/amendment_a1/a1_transport_config.json",
                "tools/a1_surface_bridge.py",
                "tools/executor_config.json",
                "tools/executor_harness.py",
            ]
            for relative_path in paths:
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"committed:{relative_path}\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "candidate"], cwd=root, check=True)
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, check=True,
                capture_output=True, text=True,
            ).stdout.strip()
            cfg = {
                "recovery_implementation": {"path": paths[1]},
                "recovery_tests": {"path": paths[2]},
                "recovery_amendment": {"path": paths[3]},
                "a1_transport_config": {"path": paths[4]},
                "ratified_bridge": {"path": paths[5]},
                "frozen_executor_config": {"path": paths[6]},
                "frozen_executor_harness": {"path": paths[7]},
            }
            recovery_path = root / "evidence/amendment_a1/infra_recovery_01/gate5"
            originals = {path: (root / path).read_bytes() for path in paths[:2]}
            for relative_path in paths[:2]:
                with self.subTest(relative_path=relative_path):
                    (root / relative_path).write_text("tampered\n", encoding="utf-8")
                    with patch.object(recovery, "verify_preserved_failed_gate5"), \
                         patch.object(recovery, "load_bound_runtime", return_value=({}, {})), \
                         patch.object(recovery, "recovery_artifact_dir", return_value=recovery_path), \
                         patch.object(recovery, "verify_recovery_ratification", return_value=commit), \
                         patch.object(recovery, "run_recovery_probe") as probe:
                        with self.assertRaisesRegex(RuntimeError, "SIGNED_TREE_WORKTREE_MISMATCH"):
                            recovery.execute_once(root, cfg)
                        probe.assert_not_called()
                    self.assertFalse(recovery_path.exists())
                    (root / relative_path).write_bytes(originals[relative_path])

    def test_production_cli_rejects_alternate_recovery_config(self):
        with self.assertRaises(SystemExit) as raised:
            recovery.main([
                "--execute-recovery-gate5", "--recovery-config", "/tmp/alternate.json"
            ])
        self.assertEqual(raised.exception.code, 2)

    def test_rate_limit_then_neutral_response_passes_in_two_calls(self):
        failure = MagicMock(returncode=1, stdout=stream_result(synthetic_error=True), stderr="")
        success = MagicMock(
            returncode=0, stdout=stream_result(result=bridge.GATE5_EXPECTED_RESPONSE), stderr=""
        )
        result, run = self.run_probe([failure, success])
        self.assertTrue(result["gate5_pass"])
        self.assertEqual(run.call_count, 2)

    def test_three_pre_response_failures_halt_without_fourth_call(self):
        failure = MagicMock(returncode=1, stdout=stream_result(synthetic_error=True), stderr="")
        result, run = self.run_probe([failure, failure, failure])
        self.assertFalse(result["gate5_pass"])
        self.assertEqual(result["failure_reason"], "INFRA_FAILURE")
        self.assertEqual(run.call_count, 3)

    def test_wrong_exact_match_response_is_not_retried(self):
        wrong = MagicMock(returncode=0, stdout=stream_result(result="wrong"), stderr="")
        result, run = self.run_probe([wrong])
        self.assertFalse(result["gate5_pass"])
        self.assertEqual(result["failure_reason"], "RESPONSE_NOT_EXACT_MATCH")
        self.assertEqual(run.call_count, 1)

    def test_empty_delivered_response_is_not_retried(self):
        empty = MagicMock(returncode=0, stdout=stream_result(result=""), stderr="")
        result, run = self.run_probe([empty])
        self.assertFalse(result["gate5_pass"])
        self.assertEqual(run.call_count, 1)
        self.assertTrue((self.artifact_dir / "responses" / "response_0.txt").is_file())
        self.assertEqual((self.artifact_dir / "responses" / "response_0.txt").read_text(), "")

    def test_model_identity_failure_is_not_retried(self):
        mismatch = MagicMock(returncode=0, stdout=stream_result(model="other-model", result="x"), stderr="")
        result, run = self.run_probe([mismatch])
        self.assertFalse(result["gate5_pass"])
        self.assertEqual(result["failure_reason"], "INFRA_FAILURE")
        self.assertEqual(run.call_count, 1)

    def test_recovery_namespace_does_not_overlap_failed_r9_gate5(self):
        cfg = {
            "failed_gate5_evidence_root": "evidence/amendment_a1/r9_execution/gate5",
            "recovery_gate5_evidence_root": "evidence/amendment_a1/infra_recovery_01/gate5",
        }
        recovery_path = recovery.recovery_artifact_dir(REPO_ROOT, cfg)
        failed_path = (REPO_ROOT / cfg["failed_gate5_evidence_root"]).resolve()
        self.assertNotEqual(recovery_path, failed_path)
        self.assertNotEqual(os.path.commonpath([str(recovery_path), str(failed_path)]), str(failed_path))

    def test_frozen_executor_files_remain_unchanged(self):
        self.assertEqual(sha256_file(REPO_ROOT / "tools" / "executor_config.json"), FROZEN_EXECUTOR_CONFIG_SHA)
        self.assertEqual(sha256_file(REPO_ROOT / "tools" / "executor_harness.py"), FROZEN_EXECUTOR_HARNESS_SHA)


if __name__ == "__main__":
    unittest.main(verbosity=2)
