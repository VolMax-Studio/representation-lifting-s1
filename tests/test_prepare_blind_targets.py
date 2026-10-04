#!/usr/bin/env python3
"""
tests/test_prepare_blind_targets.py
Unit tests and deterministic verification for tools/prepare_blind_targets.py.

Verifies:
1. Index Separation Invariant:
   POOL.tsv 0-based row positions [105, 80, 261] map to case_ids [proofnet-108, proofnet-083, proofnet-267],
   which correspond to canonical ProofNet JSONL `index` values [108, 83, 267].
   Asserts row_position != jsonl_index for all 3 cases (105 != 108, 80 != 83, 261 != 267).
2. Deterministic mechanical extraction with declaration renaming to `theorem frozen_target`.
3. Pinned byte-identical SHA-256 digests across all 3 generated target files.
4. Lean 4 baseline elaboration (`lake env lean`) on all 3 targets.
"""

import os
import sys
import json
import hashlib
import tempfile
import subprocess
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS_DIR = os.path.join(PROJECT_ROOT, "tools")
sys.path.insert(0, TOOLS_DIR)

from prepare_blind_targets import prepare_targets, FROZEN_CASES, DEFAULT_JSONL

PINNED_TARGET_SHA256 = {
    "proofnet-083": "507b4860cde42100ac319d4d9452b2e418de9bf1de67d0a2b9ab651d7732fd51",
    "proofnet-108": "8b0776c182dd39259dbb2a19037c2214a3322a95f0ab808748f699967f2213f9",
    "proofnet-267": "2eb7cdde40626e120d46eecba2c58c230298ca986e7589c38ef2db88e4879a89",
}

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

class TestPrepareBlindTargets(unittest.TestCase):

    def test_pool_row_position_vs_jsonl_index_mapping(self):
        """
        Critical regression test: POOL row position != ProofNet JSONL index.
        Row position 105 in POOL.tsv -> proofnet-108 -> JSONL index 108.
        Row position 80  in POOL.tsv -> proofnet-083 -> JSONL index 83.
        Row position 261 in POOL.tsv -> proofnet-267 -> JSONL index 267.
        """
        pool_tsv_path = os.path.join(PROJECT_ROOT, "evidence", "pool-build-local-002", "POOL.tsv")
        self.assertTrue(os.path.isfile(pool_tsv_path), f"POOL.tsv missing at {pool_tsv_path}")

        with open(pool_tsv_path, "r", encoding="utf-8") as f:
            lines = [l.strip().split("\t") for l in f if l.strip()]

        header = lines[0]
        self.assertEqual(header, ["case_id", "source_name"])
        rows = lines[1:]  # 0-indexed rows in pool

        expected_pool_mapping = [
            (105, "proofnet-108", 108, "Munkres_exercise_13_5a"),
            (80,  "proofnet-083", 83,  "Herstein_exercise_2_11_22"),
            (261, "proofnet-267", 267, "Herstein_exercise_2_11_7"),
        ]

        for row_pos, expected_cid, expected_jsonl_idx, expected_source_name in expected_pool_mapping:
            # Assert row position is NOT equal to JSONL index
            self.assertNotEqual(row_pos, expected_jsonl_idx,
                                f"Row position {row_pos} must not equal JSONL index {expected_jsonl_idx}")

            # Verify POOL.tsv row content
            row = rows[row_pos]
            self.assertEqual(row[0], expected_cid,
                             f"POOL.tsv row {row_pos} case_id mismatch: expected {expected_cid}, got {row[0]}")
            self.assertEqual(row[1], expected_source_name,
                             f"POOL.tsv row {row_pos} source_name mismatch: expected {expected_source_name}, got {row[1]}")

        # Verify FROZEN_CASES in prepare_blind_targets uses canonical JSONL indices
        self.assertEqual(FROZEN_CASES, [
            (108, "proofnet-108"),
            (83,  "proofnet-083"),
            (267, "proofnet-267"),
        ])

    def test_deterministic_target_emission_and_hashes(self):
        """
        Verifies that prepare_targets produces byte-identical files matching pinned SHA-256 digests.
        """
        self.assertTrue(os.path.isfile(DEFAULT_JSONL), f"ProofNet JSONL missing at {DEFAULT_JSONL}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            emitted = prepare_targets(DEFAULT_JSONL, tmp_dir)
            self.assertEqual(set(emitted.keys()), {"proofnet-108", "proofnet-083", "proofnet-267"})

            for cid, path in emitted.items():
                self.assertTrue(os.path.isfile(path), f"File {path} not created")
                actual_sha = sha256_file(path)
                expected_sha = PINNED_TARGET_SHA256[cid]
                self.assertEqual(
                    actual_sha, expected_sha,
                    f"SHA-256 mismatch for {cid}!\n  Expected: {expected_sha}\n  Actual:   {actual_sha}"
                )

                # Check declaration format
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.assertIn("theorem frozen_target", content, f"{cid} missing 'theorem frozen_target'")
                self.assertTrue(content.strip().endswith(":= by sorry"), f"{cid} does not end with ':= by sorry'")

    def test_lean4_elaboration(self):
        """
        Verifies that all 3 emitted target files elaborate cleanly with Lean 4.
        """
        targets_dir = os.path.join(PROJECT_ROOT, "targets")
        self.assertTrue(os.path.isdir(targets_dir), f"Targets dir missing at {targets_dir}")

        for cid, expected_sha in PINNED_TARGET_SHA256.items():
            fpath = os.path.join(targets_dir, f"{cid}.lean")
            self.assertTrue(os.path.isfile(fpath), f"Target file missing: {fpath}")
            self.assertEqual(sha256_file(fpath), expected_sha, f"Target {cid} hash modified on disk!")

            res = subprocess.run(["lake", "env", "lean", fpath], cwd=PROJECT_ROOT, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"Lean elaboration failed for {cid}:\n{res.stderr}")

    def test_source_jsonl_sha_fail_closed(self):
        """
        Verifies that prepare_targets fails closed if source JSONL SHA-256 does not match canonical pin.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            corrupt_jsonl = os.path.join(tmp_dir, "corrupt.jsonl")
            with open(corrupt_jsonl, "w", encoding="utf-8") as f:
                f.write('{"index": 1, "name": "dummy"}\n')
            with self.assertRaises(ValueError) as ctx:
                prepare_targets(corrupt_jsonl, tmp_dir)
            self.assertIn("Source ProofNet JSONL SHA-256 mismatch", str(ctx.exception))

if __name__ == "__main__":
    unittest.main()
