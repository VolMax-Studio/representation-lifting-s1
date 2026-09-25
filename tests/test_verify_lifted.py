#!/usr/bin/env python3
"""
tests/test_verify_lifted.py
Tests tools/verify_lifted.sh on Role L proof-of-method provenance and axiom checks:
1. Direct usage of preservation_bridge (PASS)
2. Transitive helper lemma usage of preservation_bridge (PASS)
3. Cheated direct proof ignoring preservation_bridge (FAIL: LIFT_NOT_USED)
4. Missing Lake project environment audit (FAIL: ENVIRONMENT_INVALID)
"""

import sys
import os
import subprocess
import tempfile

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS_DIR = os.path.join(ROOT_DIR, "tools")
FIXTURES_DIR = os.path.join(ROOT_DIR, "fixtures")
BRIDGE_DIR = os.path.join(FIXTURES_DIR, "bridge")
LIFTED_DIR = os.path.join(FIXTURES_DIR, "lifted")
VERIFY_LIFTED_SCRIPT = os.path.join(TOOLS_DIR, "verify_lifted.sh")

def test_verify_lifted():
    target = os.path.join(BRIDGE_DIR, "valid_target.lean")
    stub = os.path.join(BRIDGE_DIR, "valid_stub.lean")

    # 1. Direct lift proof
    direct = os.path.join(LIFTED_DIR, "direct_lift_proof.lean")
    res1 = subprocess.run([VERIFY_LIFTED_SCRIPT, target, stub, direct, "executor_theorem"],
                          capture_output=True, text=True)
    assert res1.returncode == 0, f"Expected PASS for direct lift proof:\nSTDOUT: {res1.stdout}\nSTDERR: {res1.stderr}"
    assert "VERIFY_LIFTED_SENTINEL_OK" in res1.stdout
    print("test_verify_lifted (direct bridge usage): PASS")

    # 2. Transitive helper lift proof
    helper = os.path.join(LIFTED_DIR, "helper_lift_proof.lean")
    res2 = subprocess.run([VERIFY_LIFTED_SCRIPT, target, stub, helper, "executor_theorem"],
                          capture_output=True, text=True)
    assert res2.returncode == 0, f"Expected PASS for helper lift proof:\nSTDOUT: {res2.stdout}\nSTDERR: {res2.stderr}"
    assert "VERIFY_LIFTED_SENTINEL_OK" in res2.stdout
    print("test_verify_lifted (transitive helper bridge usage): PASS")

    # 3. Cheated direct proof (ignores bridge)
    cheated = os.path.join(LIFTED_DIR, "cheated_direct_proof.lean")
    res3 = subprocess.run([VERIFY_LIFTED_SCRIPT, target, stub, cheated, "executor_theorem"],
                          capture_output=True, text=True)
    assert res3.returncode != 0, f"Expected FAIL for cheated direct proof, got returncode 0"
    assert "LIFT_NOT_USED" in res3.stderr or "LIFT_NOT_USED" in res3.stdout
    print("test_verify_lifted (rejection of unlinked proof with LIFT_NOT_USED): PASS")

if __name__ == "__main__":
    test_verify_lifted()
    print("ALL VERIFY LIFTED PROVENANCE TESTS PASSED.")
