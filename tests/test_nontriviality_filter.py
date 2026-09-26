#!/usr/bin/env python3
"""
tests/test_nontriviality_filter.py
Regression and adversarial test suite for Gate 1 input contract:
1. Canonical extractor (tools/extract_proofnet_statement.py):
   - Strict anchored extraction
   - Fail-closed on multiple sorry, trailing content, or format ambiguity
   - Full 367-case kill test against ProofNet-Verified JSONL
2. Tri-state fail-closed nontriviality filter (tools/nontriviality_filter.sh):
   - 0 = NONTRIVIAL (baseline elaboration with sorry succeeds, all 4 tactics fail)
   - 1 = TRIVIAL (proved by at least one of rfl, decide, linarith, ring)
   - 2 = INPUT_ERROR / BASELINE_INVALID (baseline elaboration fails, syntax error, unstripped sorry)
Part of representation-lifting-s1 experimental protocol (v0.20).
"""

import unittest
import os
import sys
import json
import tempfile
import subprocess

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS_DIR = os.path.join(PROJECT_ROOT, "tools")
sys.path.insert(0, TOOLS_DIR)

from extract_proofnet_statement import extract_canonical_statement, InputContractError

FILTER_SH = os.path.join(TOOLS_DIR, "nontriviality_filter.sh")
DEFAULT_PROOFNET_PATH = os.path.abspath(os.path.join(PROJECT_ROOT, "..", "..", "ARCHIVE_EXTERNAL", "ProofNet-Verified", "data", "proofnet-verified.jsonl"))
PROOFNET_JSONL = os.environ.get("PROOFNET_JSONL", DEFAULT_PROOFNET_PATH)

class TestGate1InputContract(unittest.TestCase):

    def run_filter(self, code: str) -> tuple[int, str, str]:
        with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False) as f:
            f.write(code)
            path = f.name
        try:
            proc = subprocess.run([FILTER_SH, path], cwd=PROJECT_ROOT, capture_output=True, text=True)
            return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
        finally:
            if os.path.exists(path):
                os.remove(path)

    # -------------------------------------------------------------------------
    # Extractor Tests
    # -------------------------------------------------------------------------

    def test_extractor_standard_entry(self):
        entry = {
            "index": 1,
            "name": "Artin_exercise_2_2_9",
            "header": "open Function\nopen scoped BigOperators",
            "helper": "",
            "formal_stmt": "theorem Artin_exercise_2_2_9 {G : Type*} [Group G] {a b : G}\n  (h : a * b = b * a) :\n  ∀ x y : closure {x | x = a ∨ x = b}, x * y = y * x := by\n  sorry"
        }
        res = extract_canonical_statement(entry)
        self.assertTrue(res.startswith("import Mathlib"))
        self.assertIn("open Function", res)
        self.assertIn("theorem Artin_exercise_2_2_9", res)
        self.assertNotIn("sorry", res)
        self.assertFalse(res.rstrip().endswith(":="))

    def test_extractor_variant_colon_equals_sorry(self):
        # Variant where statement ends with `:= sorry` rather than `:= by sorry`
        entry = {
            "index": 137,
            "name": "Pugh_exercise_2_41",
            "header": "import Mathlib\nopen Metric",
            "helper": "",
            "formal_stmt": "theorem Pugh_exercise_2_41 (E : Type*) [NormedAddCommGroup E] :\n    IsCompact (Metric.closedBall (0 : E) 1) :=\n    sorry"
        }
        res = extract_canonical_statement(entry)
        self.assertIn("theorem Pugh_exercise_2_41", res)
        self.assertNotIn("sorry", res)
        self.assertFalse(res.rstrip().endswith(":="))

    def test_extractor_with_helper_and_let(self):
        # Entry with helper definition and let := inside formal_stmt (Index 289)
        entry = {
            "index": 289,
            "name": "Munkres_exercise_13_3b",
            "header": "import Mathlib\nopen Set",
            "helper": "def my_helper : ℕ := 42",
            "formal_stmt": "theorem Munkres_exercise_13_3b : ∃ X : Type,\n    let T_inf : Set (Set X) := {t | Set.Infinite tᶜ ∨ t = ∅ ∨ t = Set.univ}\n    True := by\n  sorry"
        }
        res = extract_canonical_statement(entry)
        self.assertIn("def my_helper : ℕ := 42", res)
        self.assertIn("let T_inf", res)
        self.assertNotIn("sorry", res)

    def test_extractor_fail_closed_multiple_sorry(self):
        entry = {
            "name": "bad_entry",
            "formal_stmt": "theorem foo : True := by\n  have h : 1 = 1 := by sorry\n  sorry"
        }
        with self.assertRaises(InputContractError) as ctx:
            extract_canonical_statement(entry)
        self.assertIn("must contain exactly one 'sorry'", str(ctx.exception))

    def test_extractor_fail_closed_trailing_content_after_sorry(self):
        entry = {
            "name": "trailing_junk",
            "formal_stmt": "theorem foo : True := by sorry\n#check 42"
        }
        with self.assertRaises(InputContractError) as ctx:
            extract_canonical_statement(entry)
        self.assertIn("does not end with recognized proof placeholder", str(ctx.exception))

    def test_extractor_fail_closed_missing_fields(self):
        with self.assertRaises(InputContractError):
            extract_canonical_statement({"formal_stmt": "theorem foo : True := by sorry"})
        with self.assertRaises(InputContractError):
            extract_canonical_statement({"name": "foo"})

    def test_extractor_kill_test_all_proofnet_entries(self):
        """Kill-test: Asserts all 367 entries in ProofNet-Verified extract cleanly with zero leakage."""
        if not os.path.exists(PROOFNET_JSONL):
            self.skipTest(f"ProofNet JSONL not found at {PROOFNET_JSONL}")

        with open(PROOFNET_JSONL, "r", encoding="utf-8") as f:
            entries = [json.loads(line) for line in f if line.strip()]

        self.assertEqual(len(entries), 367, "ProofNet-Verified must contain exactly 367 entries")
        for e in entries:
            decl = extract_canonical_statement(e)
            self.assertTrue(decl.startswith("import Mathlib"), f"{e['name']}: must start with import Mathlib")
            self.assertNotIn("sorry", decl, f"{e['name']}: extracted declaration leaked 'sorry'")

    # -------------------------------------------------------------------------
    # Nontriviality Filter Tri-State Contract Tests
    # -------------------------------------------------------------------------

    def test_filter_trivial_rfl(self):
        code = "theorem test_rfl : 1 = 1"
        rc, out, _ = self.run_filter(code)
        self.assertEqual(rc, 1, f"Expected TRIVIAL (1), got {rc}: {out}")
        self.assertIn("TRIVIAL: Solved by tactic", out)

    def test_filter_trivial_decide(self):
        code = "theorem test_decide : 2 + 2 = 4"
        rc, out, _ = self.run_filter(code)
        self.assertEqual(rc, 1, f"Expected TRIVIAL (1), got {rc}: {out}")
        self.assertIn("TRIVIAL: Solved by tactic", out)

    def test_filter_trivial_ring(self):
        code = "theorem test_ring (x y : ℤ) : (x + y)^2 = x^2 + 2*x*y + y^2"
        rc, out, _ = self.run_filter(code)
        self.assertEqual(rc, 1, f"Expected TRIVIAL (1), got {rc}: {out}")
        self.assertIn("TRIVIAL: Solved by tactic", out)

    def test_filter_trivial_linarith(self):
        code = "theorem test_linarith (x y : ℤ) (h1 : x < y) (h2 : y < x) : False"
        rc, out, _ = self.run_filter(code)
        self.assertEqual(rc, 1, f"Expected TRIVIAL (1), got {rc}: {out}")
        self.assertIn("TRIVIAL: Solved by tactic", out)

    def test_filter_nontrivial_statement(self):
        # A true non-trivial statement that cannot be solved by rfl, decide, linarith, or ring
        code = "theorem test_nontrivial (n : ℕ) (h : n > 2) (x y z : ℕ) (hx : x > 0) (hy : y > 0) (hz : z > 0) : x^n + y^n ≠ z^n"
        rc, out, _ = self.run_filter(code)
        self.assertEqual(rc, 0, f"Expected NONTRIVIAL (0), got {rc}: {out}")
        self.assertIn("NONTRIVIAL: Passed all 4 basic tactic tests.", out)

    def test_filter_adversarial_syntax_error_fails_closed(self):
        # Syntax error must exit with 2 (INPUT_ERROR), never 0 (NONTRIVIAL)
        code = "theorem test_broken : 1 + + = 2"
        rc, _, err = self.run_filter(code)
        self.assertEqual(rc, 2, f"Expected INPUT_ERROR (2) on syntax error, got {rc}")
        self.assertIn("failed baseline elaboration with sorry", err)

    def test_filter_adversarial_unstripped_sorry_fails_closed(self):
        # Passing a file that still has `:= by sorry` must exit with 2, never 0
        code = "theorem test_unstripped (x : ℕ) : x = x := by sorry"
        rc, _, err = self.run_filter(code)
        self.assertEqual(rc, 2, f"Expected INPUT_ERROR (2) on unstripped sorry, got {rc}")
        self.assertIn("contains unstripped 'sorry'", err)

    def test_filter_adversarial_missing_file_fails_closed(self):
        proc = subprocess.run([FILTER_SH, "/path/does/not/exist.lean"], cwd=PROJECT_ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2, "Expected exit 2 for missing file")
        self.assertIn("does not exist", proc.stderr)

if __name__ == "__main__":
    unittest.main()
