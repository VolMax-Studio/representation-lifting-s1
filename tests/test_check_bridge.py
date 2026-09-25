#!/usr/bin/env python3
"""
tests/test_check_bridge.py
Automated regression tests for bridge verification against frozen fixtures.
Tests every decision branch of CheckBridge.lean:
1. Valid bridge linkage (PASS)
2. Syntactic tautology P ↔ P (FAIL)
3. Unrelated conclusion (FAIL)
4. Extra binder count (FAIL)
5. Dependent Pi target (PASS)
6. Existential target (PASS)
7. Same binder count but different hypothesis (FAIL: BINDER_TYPE_MISMATCH)
8. Mismatched dependent binder type (FAIL: BINDER_TYPE_MISMATCH)
9. Identity Guard: same domain and id function (FAIL: IDENTITY_GUARD)
10. Identity Guard: same domain but non-id function (PASS)
11. Custom axiom in representation layer (FAIL: FORBIDDEN_REPRESENTATION_AXIOM)
12. Mathlib target with typeclass binders and external imports (PASS)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools.check_bridge import check_bridge

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BRIDGE_DIR = os.path.join(ROOT_DIR, "fixtures", "bridge")
IDENTITY_DIR = os.path.join(ROOT_DIR, "fixtures", "identity")
MATHLIB_DIR = os.path.join(ROOT_DIR, "fixtures", "mathlib")

def test_fixtures():
    cases = [
        # (name, target_path, stub_path, expected_pass, expected_message_substring)
        ("valid_bridge", 
         os.path.join(BRIDGE_DIR, "valid_target.lean"), 
         os.path.join(BRIDGE_DIR, "valid_stub.lean"), 
         True, "BRIDGE_VALID"),
        
        ("tautological_bridge", 
         os.path.join(BRIDGE_DIR, "tautological_target.lean"), 
         os.path.join(BRIDGE_DIR, "tautological_stub.lean"), 
         False, "TAUTOLOGICAL_BRIDGE"),
        
        ("unrelated_bridge", 
         os.path.join(BRIDGE_DIR, "unrelated_target.lean"), 
         os.path.join(BRIDGE_DIR, "unrelated_stub.lean"), 
         False, "UNLINKED_TARGET"),
        
        ("extra_hyp_bridge", 
         os.path.join(BRIDGE_DIR, "extra_hyp_target.lean"), 
         os.path.join(BRIDGE_DIR, "extra_hyp_stub.lean"), 
         False, "BINDER_COUNT_MISMATCH"),
        
        ("dependent_pi_target", 
         os.path.join(BRIDGE_DIR, "dependent_pi_target.lean"), 
         os.path.join(BRIDGE_DIR, "dependent_pi_stub.lean"), 
         True, "BRIDGE_VALID"),
        
        ("existential_target", 
         os.path.join(BRIDGE_DIR, "existential_target.lean"), 
         os.path.join(BRIDGE_DIR, "existential_stub.lean"), 
         True, "BRIDGE_VALID"),
        
        ("same_count_diff_hyp",
         os.path.join(BRIDGE_DIR, "same_count_diff_hyp_target.lean"),
         os.path.join(BRIDGE_DIR, "same_count_diff_hyp_stub.lean"),
         False, "BINDER_TYPE_MISMATCH"),

        ("dependent_binder_mismatch",
         os.path.join(BRIDGE_DIR, "dependent_binder_mismatch_target.lean"),
         os.path.join(BRIDGE_DIR, "dependent_binder_mismatch_stub.lean"),
         False, "BINDER_TYPE_MISMATCH"),

        ("same_domain_id",
         os.path.join(BRIDGE_DIR, "valid_target.lean"),
         os.path.join(IDENTITY_DIR, "same_domain_id_stub.lean"),
         False, "IDENTITY_GUARD"),

        ("same_domain_non_id",
         os.path.join(BRIDGE_DIR, "valid_target.lean"),
         os.path.join(IDENTITY_DIR, "same_domain_non_id_stub.lean"),
         True, "BRIDGE_VALID"),

        ("custom_axiom",
         os.path.join(BRIDGE_DIR, "valid_target.lean"),
         os.path.join(BRIDGE_DIR, "custom_axiom_stub.lean"),
         False, "FORBIDDEN_REPRESENTATION_AXIOM"),

        ("mathlib_bridge",
         os.path.join(MATHLIB_DIR, "mathlib_target.lean"),
         os.path.join(MATHLIB_DIR, "mathlib_stub.lean"),
         True, "BRIDGE_VALID")
    ]
    
    for name, target_file, stub_file, exp_pass, exp_msg in cases:
        ok, msg = check_bridge(target_file, stub_file)
        assert ok == exp_pass, f"Fixture '{name}' expected pass={exp_pass}, got pass={ok}\nMESSAGE: {msg}"
        assert exp_msg in msg, f"Fixture '{name}' expected substring '{exp_msg}', got '{msg}'"
        print(f"Fixture '{name}': PASS (expected {exp_pass} -> {msg[:60]}...)")
        
    print(f"\nALL {len(cases)} BRIDGE FIXTURE REGRESSION TESTS PASSED.")

if __name__ == "__main__":
    test_fixtures()
