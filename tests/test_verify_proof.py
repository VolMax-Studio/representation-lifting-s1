#!/usr/bin/env python3
"""
tests/test_verify_proof.py
Tests tools/verify_proof.sh on binder targets, alpha-renaming, wrong proofs, and Mathlib targets.
"""

import sys
import os
import subprocess
import tempfile

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS_DIR = os.path.join(ROOT_DIR, "tools")
MATHLIB_DIR = os.path.join(ROOT_DIR, "fixtures", "mathlib")
VERIFY_SCRIPT = os.path.join(TOOLS_DIR, "verify_proof.sh")

def test_verify_proof():
    with tempfile.TemporaryDirectory() as tmp_dir:
        target_file = os.path.join(tmp_dir, "target.lean")
        with open(target_file, "w") as f:
            f.write("theorem frozen_target (n : Nat) (hn : 2 <= n) : n + 0 = n := by sorry\n")
            
        # 1. Valid executor proof with renamed binders (m, hm)
        valid_file = os.path.join(tmp_dir, "valid_executor.lean")
        with open(valid_file, "w") as f:
            f.write("theorem my_proof (m : Nat) (hm : 2 <= m) : m + 0 = m := by rfl\n")
            
        res_valid = subprocess.run([VERIFY_SCRIPT, target_file, valid_file, "my_proof"],
                                   capture_output=True, text=True)
        assert res_valid.returncode == 0, f"Expected PASS, got:\nSTDOUT: {res_valid.stdout}\nSTDERR: {res_valid.stderr}"
        assert "VERIFICATION_SUCCESS" in res_valid.stdout
        print("test_verify_proof (valid proof with binder renaming): PASS")
        
        # 2. Invalid proof (type mismatch)
        mismatch_file = os.path.join(tmp_dir, "mismatch_executor.lean")
        with open(mismatch_file, "w") as f:
            f.write("theorem wrong_proof (m : Nat) : m + 1 = 1 + m := by omega\n")
            
        res_mismatch = subprocess.run([VERIFY_SCRIPT, target_file, mismatch_file, "wrong_proof"],
                                      capture_output=True, text=True)
        assert res_mismatch.returncode != 0
        assert "TYPE_MISMATCH" in res_mismatch.stderr or "TYPE_MISMATCH" in res_mismatch.stdout
        print("test_verify_proof (type mismatch rejection): PASS")
        
        # 3. Forbidden escape token (sorry)
        sorry_file = os.path.join(tmp_dir, "sorry_executor.lean")
        with open(sorry_file, "w") as f:
            f.write("theorem cheated_proof (m : Nat) (hm : 2 <= m) : m + 0 = m := by sorry\n")
            
        res_sorry = subprocess.run([VERIFY_SCRIPT, target_file, sorry_file, "cheated_proof"],
                                   capture_output=True, text=True)
        assert res_sorry.returncode != 0
        assert "FAIL_CLOSED" in res_sorry.stderr or "FAIL_CLOSED" in res_sorry.stdout
        print("test_verify_proof (fail-closed sorry rejection): PASS")

        # 4. Mathlib proof verification
        m_target = os.path.join(MATHLIB_DIR, "mathlib_target.lean")
        m_proof = os.path.join(MATHLIB_DIR, "mathlib_direct_proof.lean")
        res_mathlib = subprocess.run([VERIFY_SCRIPT, m_target, m_proof, "executor_theorem"],
                                     capture_output=True, text=True)
        assert res_mathlib.returncode == 0, f"Mathlib proof verification failed:\nSTDOUT: {res_mathlib.stdout}\nSTDERR: {res_mathlib.stderr}"
        assert "VERIFICATION_SUCCESS" in res_mathlib.stdout
        print("test_verify_proof (Mathlib AddCommGroup target and proof): PASS")

        # 5. Adversarial namespace escape via _root_ (Method Mode Deny-List)
        t2_target = os.path.join(ROOT_DIR, "calibration", "fibonacci_t2.lean")
        root_esc = os.path.join(ROOT_DIR, "fixtures", "method_mode", "root_aux_forbidden.lean")
        adm_fib = os.path.join(ROOT_DIR, "admissibility", "fibonacci.json")
        res_root = subprocess.run([VERIFY_SCRIPT, t2_target, root_esc, "executor_theorem", adm_fib],
                                  capture_output=True, text=True)
        assert res_root.returncode != 0
        assert "FORBIDDEN_METHOD_MODE_CONSTANT" in res_root.stderr or "FORBIDDEN_METHOD_MODE_CONSTANT" in res_root.stdout
        print("test_verify_proof (adversarial _root_ Method Mode rejection): PASS")

        # 6. Adversarial namespace escape via explicit end (Method Mode Deny-List)
        ns_esc = os.path.join(ROOT_DIR, "fixtures", "method_mode", "namespace_escape_forbidden.lean")
        res_ns = subprocess.run([VERIFY_SCRIPT, t2_target, ns_esc, "executor_theorem", adm_fib],
                                capture_output=True, text=True)
        assert res_ns.returncode != 0
        assert "FORBIDDEN_METHOD_MODE_CONSTANT" in res_ns.stderr or "FORBIDDEN_METHOD_MODE_CONSTANT" in res_ns.stdout
        print("test_verify_proof (adversarial explicit namespace escape Method Mode rejection): PASS")

if __name__ == "__main__":
    test_verify_proof()
    print("ALL VERIFY PROOF TESTS PASSED.")
