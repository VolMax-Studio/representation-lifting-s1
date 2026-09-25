#!/usr/bin/env python3
"""
tests/test_executor_harness.py
Regression tests for tools/executor_harness.py state machine (v0.6).
Tests:
1. Role S interaction loop and receipt emission.
2. Role L structural proof verification (preservation_bridge + lifted_theorem).
3. Truncation detection and normalization (OUTPUT_TRUNCATED).
4. Sequential multi-theorem calibration state machine (run_calibration_family).
"""

import sys
import os
import tempfile
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools.executor_harness import ExecutorStateMachine, run_calibration_family, is_stop_reason_truncated

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURES_DIR = os.path.join(ROOT_DIR, "fixtures")
BRIDGE_DIR = os.path.join(FIXTURES_DIR, "bridge")

def test_harness_role_s():
    with tempfile.TemporaryDirectory() as tmp_dir:
        target_file = os.path.join(BRIDGE_DIR, "valid_target.lean")
        manifest_file = os.path.join(tmp_dir, "manifest.md")
        with open(manifest_file, "w") as f:
            f.write("Standard Method Mode rules.\n")

        # Mock turn 1: Fails (missing liftT)
        # Mock turn 2: Passes with LiftedClaim and BridgeProp
        def mock_s(role, turn, msgs):
            if turn == 1:
                return ("Here is attempt:\n```lean\nabbrev LiftDom := Nat\nabbrev LiftCod := Nat × Unit\n```", "end_turn", False)
            else:
                return ("""Here is valid stub:
```lean
abbrev LiftDom := Nat
abbrev LiftCod := Nat × Unit

def liftT (n : LiftDom) : LiftCod := (n, ())
def invariant (p : LiftCod) : Nat := p.1

def LiftedClaim : Prop :=
  ∀ (m : Nat), invariant (liftT m) + 0 = invariant (liftT m)

def BridgeProp : Prop :=
  ∀ (m : Nat), (m + 0 = m) ↔ (invariant (liftT m) + 0 = invariant (liftT m))
```""", "end_turn", False)

        machine = ExecutorStateMachine("S", target_file, manifest_file, "claude-sonnet-4-6", mock_generator=mock_s)
        receipt = machine.run()
        assert receipt["final_status"] == "COMPLETE"
        assert receipt["turns_consumed"] == 2
        assert receipt["receipt_type"] == "hash_addressed_execution_receipt"
        print("test_harness_role_s: PASS")

def test_harness_role_l():
    with tempfile.TemporaryDirectory() as tmp_dir:
        target_file = os.path.join(BRIDGE_DIR, "valid_target.lean")
        stub_file = os.path.join(BRIDGE_DIR, "valid_stub.lean")
        manifest_file = os.path.join(tmp_dir, "manifest.md")
        with open(manifest_file, "w") as f:
            f.write("Standard Method Mode rules.\n")

        # Valid Role L structural proof
        def mock_l(role, turn, msgs):
            return ("""```lean
theorem preservation_bridge : BridgeProp := by
  intro m
  rfl

theorem lifted_theorem : LiftedClaim := by
  intro m
  rfl
```""", "end_turn", False)

        machine = ExecutorStateMachine("L", target_file, manifest_file, "claude-sonnet-4-6",
                                       frozen_prefix_path=stub_file, mock_generator=mock_l)
        receipt = machine.run()
        assert receipt["final_status"] == "COMPLETE"
        assert receipt["turns_consumed"] == 1
        assert receipt["verified_footprint_tokens"] is not None
        assert receipt["verified_footprint_tokens"] > 30
        print(f"test_harness_role_l (structural verification passed, footprint {receipt['verified_footprint_tokens']}): PASS")

def test_harness_truncation():
    assert is_stop_reason_truncated("max_tokens") is True
    assert is_stop_reason_truncated("length") is True
    assert is_stop_reason_truncated("end_turn") is False
    assert is_stop_reason_truncated("stop") is False

    with tempfile.TemporaryDirectory() as tmp_dir:
        target_file = os.path.join(BRIDGE_DIR, "valid_target.lean")
        manifest_file = os.path.join(tmp_dir, "manifest.md")
        with open(manifest_file, "w") as f:
            f.write("Standard rules.\n")

        def mock_trunc(role, turn, msgs):
            return ("```lean\ntheorem executor_theorem (m : Nat) : m + 0 = m := by ", "max_tokens", False)

        # 1 turn max for quick test
        machine = ExecutorStateMachine("D", target_file, manifest_file, "claude-sonnet-4-6", mock_generator=mock_trunc)
        machine.max_turns = 1
        receipt = machine.run()
        assert receipt["final_status"] == "OUTPUT_TRUNCATED"
        print("test_harness_truncation (OUTPUT_TRUNCATED classification): PASS")

def test_harness_calibration():
    # Test mock calibration family flow
    def mock_calib(role, turn, msgs):
        if role == "D":
            return ("```lean\ntheorem executor_theorem : True := trivial\n```", "end_turn", False)
        elif role == "S":
            return ("""```lean
abbrev LiftDom := Nat
abbrev LiftCod := Nat
def liftT (n : LiftDom) : LiftCod := n + 1
def LiftedClaim : Prop := True
def BridgeProp : Prop := True ↔ True
```""", "end_turn", False)
        elif role == "L":
            return ("""```lean
theorem preservation_bridge : BridgeProp := by constructor <;> intro _ <;> trivial
theorem lifted_theorem : LiftedClaim := trivial
```""", "end_turn", False)
        return ("", "end_turn", True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        t1 = os.path.join(tmp_dir, "mockfam_t1.lean")
        t2 = os.path.join(tmp_dir, "mockfam_t2.lean")
        with open(t1, "w") as f:
            f.write("theorem frozen_target : True := by sorry\n")
        with open(t2, "w") as f:
            f.write("theorem frozen_target : True := by sorry\n")

        import tools.executor_harness as eh
        orig_root = eh.ROOT_DIR
        try:
            eh.ROOT_DIR = tmp_dir
            calib_dir = os.path.join(tmp_dir, "calibration")
            os.makedirs(calib_dir, exist_ok=True)
            import shutil
            shutil.copy(t1, os.path.join(calib_dir, "mockfam_t1.lean"))
            shutil.copy(t2, os.path.join(calib_dir, "mockfam_t2.lean"))
            adm_dir = os.path.join(tmp_dir, "admissibility")
            os.makedirs(adm_dir, exist_ok=True)
            with open(os.path.join(adm_dir, "mockfam.json"), "w") as f:
                json.dump({"prohibited_constants": []}, f)

            report = run_calibration_family("mockfam", "claude-sonnet-4-6", mock_generator=mock_calib)
            assert "direct" in report
            assert "lifted" in report
            assert report["schema_version"] == "v0.6"
            print("test_harness_calibration (H1 calibration state machine execution): PASS")
        finally:
            eh.ROOT_DIR = orig_root

if __name__ == "__main__":
    test_harness_role_s()
    test_harness_role_l()
    test_harness_truncation()
    test_harness_calibration()
    print("ALL HARNESS STATE MACHINE TESTS PASSED.")
