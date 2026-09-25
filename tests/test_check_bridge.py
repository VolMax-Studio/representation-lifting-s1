#!/usr/bin/env python3
"""
tests/test_check_bridge.py
Automated regression tests for bridge verification against the 6 frozen fixtures.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools.check_bridge import check_bridge

FIXTURES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures", "bridge"))

def test_fixtures():
    cases = [
        # (name, target, stub, expected_pass, expected_message_substring)
        ("valid_bridge", "valid_target.lean", "valid_stub.lean", True, "BRIDGE_VALID"),
        ("tautological_bridge", "tautological_target.lean", "tautological_stub.lean", False, "TAUTOLOGICAL_BRIDGE"),
        ("unrelated_bridge", "unrelated_target.lean", "unrelated_stub.lean", False, "UNLINKED_TARGET"),
        ("extra_hyp_bridge", "extra_hyp_target.lean", "extra_hyp_stub.lean", False, "EXTRA_HYPOTHESIS"),
        ("dependent_pi_target", "dependent_pi_target.lean", "dependent_pi_stub.lean", True, "BRIDGE_VALID"),
        ("existential_target", "existential_target.lean", "existential_stub.lean", True, "BRIDGE_VALID"),
    ]
    
    for name, target_file, stub_file, exp_pass, exp_msg in cases:
        t_path = os.path.join(FIXTURES_DIR, target_file)
        s_path = os.path.join(FIXTURES_DIR, stub_file)
        
        ok, msg = check_bridge(t_path, s_path)
        assert ok == exp_pass, f"Fixture '{name}' expected pass={exp_pass}, got pass={ok} (msg: {msg})"
        assert exp_msg in msg, f"Fixture '{name}' expected substring '{exp_msg}', got '{msg}'"
        print(f"Fixture '{name}': PASS (expected {exp_pass} -> {msg})")
        
    print("ALL BRIDGE FIXTURE REGRESSION TESTS PASSED.")

if __name__ == "__main__":
    test_fixtures()
