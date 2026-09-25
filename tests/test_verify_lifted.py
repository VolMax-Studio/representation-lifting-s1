#!/usr/bin/env python3
"""
tests/test_verify_lifted.py
Tests tools/verify_lifted.sh on Role L structural proof verification:
1. Direct usage of LiftedClaim and preservation_bridge (PASS)
2. Transitive helper lemma in lifted proof (PASS)
3. Circular cheat: lifted_theorem proves itself through preservation_bridge (FAIL: CIRCULAR_LIFT_DEPENDENCY)
4. Dead bridge direct proof cheat: proves target directly with dummy have _ := preservation_bridge (FAIL: lifted_theorem missing)
5. Method Mode deny-list enforcement in lifted declarations (FAIL: FORBIDDEN_METHOD_MODE_CONSTANT)
"""

import sys
import os
import subprocess
import tempfile
import json

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
    res1 = subprocess.run([VERIFY_LIFTED_SCRIPT, target, stub, direct],
                          capture_output=True, text=True)
    assert res1.returncode == 0, f"Expected PASS for direct lift proof:\nSTDOUT: {res1.stdout}\nSTDERR: {res1.stderr}"
    assert "VERIFY_LIFTED_SENTINEL_OK" in res1.stdout
    print("test_verify_lifted (direct bridge + lifted_theorem): PASS")

    # 2. Transitive helper lift proof
    helper = os.path.join(LIFTED_DIR, "helper_lift_proof.lean")
    res2 = subprocess.run([VERIFY_LIFTED_SCRIPT, target, stub, helper],
                          capture_output=True, text=True)
    assert res2.returncode == 0, f"Expected PASS for helper lift proof:\nSTDOUT: {res2.stdout}\nSTDERR: {res2.stderr}"
    assert "VERIFY_LIFTED_SENTINEL_OK" in res2.stdout
    print("test_verify_lifted (transitive helper in lifted domain): PASS")

    # 3. Circular cheat (lifted_theorem uses preservation_bridge)
    cheated = os.path.join(LIFTED_DIR, "cheated_direct_proof.lean")
    res3 = subprocess.run([VERIFY_LIFTED_SCRIPT, target, stub, cheated],
                          capture_output=True, text=True)
    assert res3.returncode != 0, f"Expected FAIL for circular cheat, got returncode 0"
    assert "CIRCULAR_LIFT_DEPENDENCY" in res3.stderr or "CIRCULAR_LIFT_DEPENDENCY" in res3.stdout
    print("test_verify_lifted (circularity guard rejects lifted_theorem depending on bridge): PASS")

    # 3b. Transitive circular cheat (lifted_theorem -> helper -> preservation_bridge)
    trans_cheated = os.path.join(LIFTED_DIR, "transitive_circular_cheat.lean")
    res3b = subprocess.run([VERIFY_LIFTED_SCRIPT, target, stub, trans_cheated],
                           capture_output=True, text=True)
    assert res3b.returncode != 0, f"Expected FAIL for transitive circular cheat, got returncode 0"
    assert "CIRCULAR_LIFT_DEPENDENCY" in res3b.stderr or "CIRCULAR_LIFT_DEPENDENCY" in res3b.stdout
    print("test_verify_lifted (transitive circularity guard via helper rejects dependency): PASS")

    # 3c. Adversarial root_aux circular escape
    root_circ = os.path.join(LIFTED_DIR, "root_aux_circular.lean")
    res3c = subprocess.run([VERIFY_LIFTED_SCRIPT, target, stub, root_circ],
                           capture_output=True, text=True)
    assert res3c.returncode != 0, f"Expected FAIL for root_aux circular escape, got returncode 0"
    assert "CIRCULAR_LIFT_DEPENDENCY" in res3c.stderr or "CIRCULAR_LIFT_DEPENDENCY" in res3c.stdout
    print("test_verify_lifted (module-provenance rejects _root_.aux circularity escape): PASS")

    # 3d. Adversarial namespace escape circular
    ns_circ = os.path.join(LIFTED_DIR, "namespace_escape_circular.lean")
    res3d = subprocess.run([VERIFY_LIFTED_SCRIPT, target, stub, ns_circ],
                           capture_output=True, text=True)
    assert res3d.returncode != 0, f"Expected FAIL for namespace escape circular, got returncode 0"
    assert "CIRCULAR_LIFT_DEPENDENCY" in res3d.stderr or "CIRCULAR_LIFT_DEPENDENCY" in res3d.stdout
    print("test_verify_lifted (module-provenance rejects namespace-escape circularity): PASS")

    # 3e. Adversarial _aux name escape circular
    aux_circ = os.path.join(LIFTED_DIR, "aux_escape_circular.lean")
    res3e = subprocess.run([VERIFY_LIFTED_SCRIPT, target, stub, aux_circ],
                           capture_output=True, text=True)
    assert res3e.returncode != 0, f"Expected FAIL for _aux name escape circular, got returncode 0"
    assert "CIRCULAR_LIFT_DEPENDENCY" in res3e.stderr or "CIRCULAR_LIFT_DEPENDENCY" in res3e.stdout
    print("test_verify_lifted (module-provenance rejects _aux name escape circularity): PASS")

    # 4. Dead bridge direct proof cheat (only proves executor_theorem with dummy have)
    dead = os.path.join(LIFTED_DIR, "dead_bridge_direct_proof.lean")
    res4 = subprocess.run([VERIFY_LIFTED_SCRIPT, target, stub, dead],
                          capture_output=True, text=True)
    assert res4.returncode != 0, f"Expected FAIL for dead bridge cheat, got returncode 0"
    assert "lifted_theorem" in res4.stderr or "lifted_theorem" in res4.stdout
    print("test_verify_lifted (dead bridge bypass rejected due to missing lifted_theorem): PASS")

    # 5. Method Mode deny-list enforcement in lifted candidate
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"prohibited_constants": ["Nat.add_comm"]}, f)
        adm_file = f.name

    with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False) as f:
        f.write("""theorem preservation_bridge : BridgeProp := by
  intro m
  rfl

theorem lifted_theorem : LiftedClaim := by
  intro m
  have _ := Nat.add_comm m 0
  rfl
""")
        cand_violator = f.name

    try:
        res5 = subprocess.run([VERIFY_LIFTED_SCRIPT, target, stub, cand_violator, adm_file],
                              capture_output=True, text=True)
        assert res5.returncode != 0, f"Expected FAIL for prohibited constant usage in lifted theorem"
        assert "FORBIDDEN_METHOD_MODE_CONSTANT" in res5.stderr or "FORBIDDEN_METHOD_MODE_CONSTANT" in res5.stdout
        print("test_verify_lifted (Method Mode deny-list rejection in lifted proof): PASS")
    finally:
        os.remove(adm_file)
        os.remove(cand_violator)

    # 6. Adversarial elab_rules command elaborator hijack
    elab_hijack = os.path.join(ROOT_DIR, "fixtures", "security", "elab_rules_eval_hijack.lean")
    res6 = subprocess.run([VERIFY_LIFTED_SCRIPT, target, stub, elab_hijack],
                          capture_output=True, text=True)
    assert res6.returncode != 0, f"Expected FAIL for elab_rules hijack in lifted verification, got returncode 0"
    assert "VERIFY_LIFTED_FAILED" in res6.stderr or "FAIL_CLOSED" in res6.stderr or "VERIFY_LIFTED_FAILED" in res6.stdout
    print("test_verify_lifted (adversarial elab_rules hijack rejected): PASS")

    # 7. Adversarial macro_rules syntax hijack
    macro_hijack = os.path.join(ROOT_DIR, "fixtures", "security", "macro_rules_eval_hijack.lean")
    res7 = subprocess.run([VERIFY_LIFTED_SCRIPT, target, stub, macro_hijack],
                          capture_output=True, text=True)
    assert res7.returncode != 0, f"Expected FAIL for macro_rules hijack in lifted verification, got returncode 0"
    assert "VERIFY_LIFTED_FAILED" in res7.stderr or "FAIL_CLOSED" in res7.stderr or "VERIFY_LIFTED_FAILED" in res7.stdout
    print("test_verify_lifted (adversarial macro_rules hijack rejected): PASS")

if __name__ == "__main__":
    test_verify_lifted()
    print("ALL VERIFY LIFTED PROVENANCE & ARCHITECTURE TESTS PASSED.")
