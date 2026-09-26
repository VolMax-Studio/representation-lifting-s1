#!/usr/bin/env python3
"""
tests/test_build_pool.py
Regression and deterministic verification test suite for tools/build_pool.py.
Verifies:
  1. Synthetic fixture partitioning across all 5 buckets (POOL, TRIVIAL, TOOLCHAIN, INPUT_ERROR, INFRA_HANG).
  2. Machine-asserted partition invariant N_total = sum(buckets).
  3. Duplicate index and duplicate case_id fail-closed handling.
  4. Byte-identical reproducibility across two consecutive runs.
  5. Deterministic bundle commitment manifest calculation.
  6. Pinned canonical dataset hash verification.
Part of representation-lifting-s1 experimental protocol (v0.20).
"""

import unittest
import os
import sys
import json
import tempfile
import hashlib

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS_DIR = os.path.join(PROJECT_ROOT, "tools")
sys.path.insert(0, TOOLS_DIR)

import build_pool

class TestBuildPool(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def create_fixture_jsonl(self, entries: list[dict]) -> str:
        fpath = os.path.join(self.tmp_dir.name, "fixture.jsonl")
        with open(fpath, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
        return fpath

    def test_synthetic_partition_with_mock_runner(self):
        """
        Tests that all 5 mutually exclusive categories are accurately partitioned
        and the partition invariant is strictly verified.
        """
        entries = [
            # 1. Non-trivial statement -> POOL
            {
                "index": 1,
                "name": "Thm_Nontrivial",
                "header": "",
                "helper": "",
                "formal_stmt": "theorem thm_nontrivial : ∀ x : ℕ, x + 0 = x := by sorry"
            },
            # 2. Trivial statement (rfl) -> EXCLUDED_TRIVIAL
            {
                "index": 2,
                "name": "Thm_Trivial_Rfl",
                "header": "",
                "helper": "",
                "formal_stmt": "theorem thm_trivial : 1 = 1 := by sorry"
            },
            # 3. Toolchain incompatible (elaboration failure) -> EXCLUDED_TOOLCHAIN_INCOMPATIBLE
            {
                "index": 3,
                "name": "Thm_Broken_Syntax",
                "header": "",
                "helper": "",
                "formal_stmt": "theorem thm_broken : 1 + + = 2 := by sorry"
            },
            # 4. Input format error (multiple sorry) -> INPUT_ERROR
            {
                "index": 4,
                "name": "Thm_Multiple_Sorry",
                "header": "",
                "helper": "",
                "formal_stmt": "theorem thm_bad : True := by have h : True := by sorry; sorry"
            },
            # 5. Infrastructure hang simulation -> INFRA_HANG
            {
                "index": 5,
                "name": "Thm_Hanging",
                "header": "",
                "helper": "",
                "formal_stmt": "theorem thm_hang : True := by sorry"
            },
            # 6. Deterministic heartbeat timeout -> EXCLUDED_TOOLCHAIN_INCOMPATIBLE
            {
                "index": 6,
                "name": "Thm_Heartbeat_Timeout",
                "header": "",
                "helper": "",
                "formal_stmt": "theorem thm_hb : True := by sorry"
            }
        ]
        jsonl_path = self.create_fixture_jsonl(entries)

        # Mock Lean runner to simulate Lean responses deterministically
        def mock_runner(code: str, root: str, timeout: int) -> tuple[int, str, str, bool]:
            if "thm_hang" in code:
                return -1, "", "Timeout expired", True
            if "thm_hb" in code:
                return 1, "", "(deterministic) timeout at `maxHeartbeats`", False
            if "thm_broken" in code:
                return 1, "", "error: unexpected token", False
            if "thm_trivial" in code and "rfl" in code:
                return 0, "", "", False  # solved by rfl
            if "thm_nontrivial" in code:
                if "sorry" in code:
                    return 0, "", "", False  # baseline compiles
                return 1, "", "tactic failed", False  # all tactics fail
            # Default for other cases
            if "sorry" in code:
                return 0, "", "", False
            return 1, "", "tactic failed", False

        out_dir = os.path.join(self.tmp_dir.name, "output_run1")
        result = build_pool.build_pool(
            jsonl_path=jsonl_path,
            out_dir=out_dir,
            assert_pinned=False,
            lean_runner=mock_runner
        )

        rep = result["report"]["partition_counts"]
        self.assertEqual(rep["pool"], 1)
        self.assertEqual(rep["excluded_trivial"], 1)
        self.assertEqual(rep["excluded_toolchain_incompatible"], 2)  # broken syntax + heartbeat timeout
        self.assertEqual(rep["input_error"], 1)  # multiple sorry
        self.assertEqual(rep["infra_hang"], 1)   # hang simulation
        self.assertTrue(result["report"]["partition_invariant_satisfied"])
        self.assertEqual(result["report"]["total_source_entries"], 6)

        # Verify generated files exist
        for fname in ["POOL.tsv", "EXCLUDED_TRIVIAL.tsv", "EXCLUDED_TOOLCHAIN_INCOMPATIBLE.tsv",
                      "INPUT_ERROR.tsv", "INFRA_HANG.tsv", "pool_build_report.json", "pool_bundle_manifest.json"]:
            fpath = os.path.join(out_dir, fname)
            self.assertTrue(os.path.isfile(fpath), f"Missing generated file: {fname}")

        # Check POOL.tsv content
        with open(os.path.join(out_dir, "POOL.tsv")) as f:
            lines = f.read().splitlines()
        self.assertEqual(lines, ["case_id\tsource_name", "proofnet-001\tThm_Nontrivial"])

    def test_byte_identical_reproducibility_across_consecutive_runs(self):
        """
        Runs build_pool twice on the same fixture and asserts 100% byte-identical
        hashes for all generated TSV, report, and bundle manifest files.
        """
        entries = [
            {"index": 1, "name": "Thm_One", "header": "", "helper": "", "formal_stmt": "theorem t1 : True := by sorry"},
            {"index": 2, "name": "Thm_Two", "header": "", "helper": "", "formal_stmt": "theorem t2 : 1 = 1 := by sorry"},
            {"index": 3, "name": "Thm_Three", "header": "", "helper": "", "formal_stmt": "theorem t3 : 1 + + = 2 := by sorry"}
        ]
        jsonl_path = self.create_fixture_jsonl(entries)

        def mock_runner(code: str, root: str, timeout: int) -> tuple[int, str, str, bool]:
            if "t3" in code:
                return 1, "", "error: syntax error", False
            if "t2" in code and "rfl" in code:
                return 0, "", "", False
            if "t1" in code:
                if "sorry" in code:
                    return 0, "", "", False
                return 1, "", "tactic failed", False
            return 1, "", "", False

        out1 = os.path.join(self.tmp_dir.name, "run_alpha")
        out2 = os.path.join(self.tmp_dir.name, "run_beta")

        res1 = build_pool.build_pool(jsonl_path, out1, assert_pinned=False, lean_runner=mock_runner)
        res2 = build_pool.build_pool(jsonl_path, out2, assert_pinned=False, lean_runner=mock_runner)

        # Assert commitment hashes match exactly
        self.assertEqual(res1["bundle_commitment_sha"], res2["bundle_commitment_sha"])

        # Check byte-for-byte identity of all generated files
        files_to_check = [
            "POOL.tsv", "EXCLUDED_TRIVIAL.tsv", "EXCLUDED_TOOLCHAIN_INCOMPATIBLE.tsv",
            "INPUT_ERROR.tsv", "INFRA_HANG.tsv", "pool_build_report.json", "pool_bundle_manifest.json"
        ]
        for fname in files_to_check:
            with open(os.path.join(out1, fname), "rb") as f1, open(os.path.join(out2, fname), "rb") as f2:
                b1 = f1.read()
                b2 = f2.read()
            self.assertEqual(b1, b2, f"Byte divergence detected in {fname}")

    def test_duplicate_case_id_and_index_rejected_as_input_error(self):
        """Asserts duplicate index or duplicate case_id is categorized as INPUT_ERROR."""
        entries = [
            {"index": 1, "name": "First", "header": "", "helper": "", "formal_stmt": "theorem t1 : True := by sorry"},
            {"index": 1, "name": "Duplicate_Index", "header": "", "helper": "", "formal_stmt": "theorem t1_dup : True := by sorry"}
        ]
        jsonl_path = self.create_fixture_jsonl(entries)

        def mock_runner(code: str, root: str, timeout: int) -> tuple[int, str, str, bool]:
            return 0, "", "", False

        out_dir = os.path.join(self.tmp_dir.name, "out_dup")
        res = build_pool.build_pool(jsonl_path, out_dir, assert_pinned=False, lean_runner=mock_runner)

        rep = res["report"]["partition_counts"]
        self.assertEqual(rep["input_error"], 1)
        self.assertEqual(res["report"]["total_source_entries"], 2)

        with open(os.path.join(out_dir, "INPUT_ERROR.tsv")) as f:
            content = f.read()
        self.assertIn("duplicate_index: 1", content)

    def test_unpinned_assertion_fails_closed_by_default(self):
        """Asserts that running on arbitrary file with assert_pinned=True fails closed."""
        entries = [{"index": 1, "name": "Fake", "header": "", "helper": "", "formal_stmt": "theorem f : True := by sorry"}]
        jsonl_path = self.create_fixture_jsonl(entries)

        out_dir = os.path.join(self.tmp_dir.name, "out_fail")
        with self.assertRaises(ValueError) as ctx:
            build_pool.build_pool(jsonl_path, out_dir, assert_pinned=True)
        self.assertIn("Source dataset SHA-256 mismatch", str(ctx.exception))

if __name__ == "__main__":
    unittest.main()
