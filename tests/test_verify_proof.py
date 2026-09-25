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

        # 7. Adversarial _aux name escape (Method Mode Deny-List)
        aux_esc = os.path.join(ROOT_DIR, "fixtures", "method_mode", "aux_escape_forbidden.lean")
        res_aux = subprocess.run([VERIFY_SCRIPT, t2_target, aux_esc, "executor_theorem", adm_fib],
                                 capture_output=True, text=True)
        assert res_aux.returncode != 0
        assert "FORBIDDEN_METHOD_MODE_CONSTANT" in res_aux.stderr or "FORBIDDEN_METHOD_MODE_CONSTANT" in res_aux.stdout
        print("test_verify_proof (adversarial _aux name escape Method Mode rejection): PASS")

        # 8. Adversarial skipKernelTC security escape
        skip_tc = os.path.join(ROOT_DIR, "fixtures", "security", "skip_kernel_tc.lean")
        res_tc = subprocess.run([VERIFY_SCRIPT, target_file, skip_tc, "fake_thm"],
                                capture_output=True, text=True)
        assert res_tc.returncode != 0
        assert "FAIL_CLOSED" in res_tc.stderr or "FAIL_CLOSED" in res_tc.stdout
        print("test_verify_proof (adversarial skipKernelTC fail-closed rejection): PASS")

        # 9. Adversarial run_cmd meta-programming escape
        meta_cheat = os.path.join(ROOT_DIR, "fixtures", "security", "run_cmd_meta_cheat.lean")
        res_mc = subprocess.run([VERIFY_SCRIPT, target_file, meta_cheat, "fake_thm"],
                                capture_output=True, text=True)
        assert res_mc.returncode != 0
        assert "FAIL_CLOSED" in res_mc.stderr or "FAIL_CLOSED" in res_mc.stdout
        print("test_verify_proof (adversarial run_cmd meta cheat fail-closed rejection): PASS")

        # 10. Adversarial run_cmd filesystem write escape
        fs_write = os.path.join(ROOT_DIR, "fixtures", "security", "run_cmd_fs_write.lean")
        res_fs = subprocess.run([VERIFY_SCRIPT, target_file, fs_write, "fake_thm"],
                                capture_output=True, text=True)
        assert res_fs.returncode != 0
        assert "FAIL_CLOSED" in res_fs.stderr or "FAIL_CLOSED" in res_fs.stdout
        print("test_verify_proof (adversarial run_cmd filesystem write fail-closed rejection): PASS")

        # 11. Adversarial elab_rules command elaborator hijack
        # Invariant: Malicious elaborator registers successfully, leanchecker passes kernel replay,
        # but standalone compiled adjudicator executes untainted MetaM verification and rejects bogus theorem.
        elab_hijack = os.path.join(ROOT_DIR, "fixtures", "security", "elab_rules_eval_hijack.lean")
        res_elab = subprocess.run([VERIFY_SCRIPT, target_file, elab_hijack, "candidate_fake_thm"],
                                  capture_output=True, text=True)
        assert res_elab.returncode != 0, "Expected FAIL for elab_rules hijack candidate, got returncode 0"
        assert "VERIFICATION_FAILED" in res_elab.stderr or "VERIFICATION_FAILED" in res_elab.stdout
        print("test_verify_proof (adversarial elab_rules hijack rejected under compiled verifier): PASS")

        # 12. Adversarial macro_rules syntax hijack
        # Invariant: Malicious syntax macro registers successfully, leanchecker passes,
        # but compiled verifier executable is immune to command dispatch hijacking and rejects bogus theorem.
        macro_hijack = os.path.join(ROOT_DIR, "fixtures", "security", "macro_rules_eval_hijack.lean")
        res_macro = subprocess.run([VERIFY_SCRIPT, target_file, macro_hijack, "candidate_fake_thm"],
                                   capture_output=True, text=True)
        assert res_macro.returncode != 0, "Expected FAIL for macro_rules hijack candidate, got returncode 0"
        assert "VERIFICATION_FAILED" in res_macro.stderr or "VERIFICATION_FAILED" in res_macro.stdout
        print("test_verify_proof (adversarial macro_rules hijack rejected under compiled verifier): PASS")

if __name__ == "__main__":
    test_verify_proof()
    print("ALL VERIFY PROOF TESTS PASSED.")
