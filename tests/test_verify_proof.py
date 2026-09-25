#!/usr/bin/env python3
"""
tests/test_verify_proof.py
Tests tools/verify_proof.sh on binder targets, alpha-renaming, and wrong proofs.
"""

import sys
import os
import subprocess
import tempfile

TOOLS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools"))
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

if __name__ == "__main__":
    test_verify_proof()
    print("ALL VERIFY PROOF TESTS PASSED.")
