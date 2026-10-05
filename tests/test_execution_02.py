#!/usr/bin/env python3

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import execution_02 as e2


class TestExecution02(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(e2.MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_candidate_bindings_and_prior_tags_verify(self):
        e2.verify_candidate(self.manifest)

    def test_policy_is_finite_and_deterministic(self):
        policy = self.manifest["availability_policy"]
        self.assertEqual(policy["max_attempts_per_logical_turn"], 4)
        self.assertEqual(policy["backoff_seconds"], [21600, 86400, 259200])
        self.assertEqual(policy["retry_eligibility"],
                         "PRE_RESPONSE_TRANSPORT_FAILURE_AND_RESPONSE_DELIVERED_FALSE_ONLY")
        self.assertEqual(policy["delivered_response_disposition"], "FINAL_NON_RETRYABLE")

    def test_runtime_override_does_not_modify_frozen_config(self):
        frozen_path = REPO_ROOT / self.manifest["frozen_executor_config"]["path"]
        before = frozen_path.read_bytes()
        runtime = e2.runtime_executor_config(self.manifest)
        self.assertEqual(runtime["transport_policy"]["max_attempts_per_turn"], 4)
        self.assertEqual(runtime["transport_policy"]["backoff_seconds"],
                         [21600, 86400, 259200])
        self.assertEqual(frozen_path.read_bytes(), before)

    def test_gate5_window_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "GATE5_TOO_EARLY"):
            e2.require_gate5_window(
                self.manifest, datetime(2026, 10, 6, tzinfo=timezone.utc)
            )
        with self.assertRaisesRegex(RuntimeError, "GATE5_START_WINDOW_EXPIRED"):
            e2.require_gate5_window(
                self.manifest, datetime(2026, 10, 20, tzinfo=timezone.utc)
            )

    def test_availability_sleep_is_excluded_from_virtual_clock(self):
        elapsed = [0.0]
        def fake_sleep(seconds):
            elapsed[0] += seconds
        clock = e2.AvailabilityClock(sleeper=fake_sleep)
        with patch.object(e2.real_time, "monotonic", side_effect=lambda: elapsed[0]), \
             patch.object(e2.real_time, "time", side_effect=lambda: 1000.0 + elapsed[0]), \
             patch.object(e2.real_time, "perf_counter", side_effect=lambda: 2000.0 + elapsed[0]):
            before = (clock.time(), clock.monotonic(), clock.perf_counter())
            clock.sleep(21600)
            after = (clock.time(), clock.monotonic(), clock.perf_counter())
        self.assertEqual(before, after)

    def test_gate5_refuses_existing_namespace_before_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "gate5"
            existing.mkdir()
            with patch.object(e2, "verify_candidate"), \
                 patch.object(e2, "verify_execution_ratification", return_value="a" * 40), \
                 patch.object(e2, "verify_signed_tree"), \
                 patch.object(e2, "require_gate5_window"), \
                 patch.object(e2, "gate5_dir", return_value=existing), \
                 patch.object(e2.bridge, "run_gate5_probe") as probe:
                with self.assertRaisesRegex(RuntimeError, "ALREADY_STARTED"):
                    e2.run_gate5(self.manifest)
                probe.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
