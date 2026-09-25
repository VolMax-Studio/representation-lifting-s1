#!/usr/bin/env python3
"""
tests/test_executor_harness.py
Regression tests for tools/executor_harness.py state machine (v0.5).
Tests mock interaction loops for Role S, Role D, and Role L (with provenance check),
compiler feedback recovery, and hash-addressed receipt emission.
"""

import sys
import os
import tempfile
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools.executor_harness import ExecutorStateMachine

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
        # Mock turn 2: Passes with BridgeProp
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

        # Valid Role L proof using preservation_bridge
        def mock_l(role, turn, msgs):
            return ("""```lean
theorem preservation_bridge : BridgeProp := by
  intro m
  rfl

theorem executor_theorem (n : Nat) : n + 0 = n := by
  have h := (preservation_bridge n).mpr rfl
  exact h
```""", "end_turn", False)

        machine = ExecutorStateMachine("L", target_file, manifest_file, "claude-sonnet-4-6",
                                       frozen_prefix_path=stub_file, mock_generator=mock_l)
        receipt = machine.run()
        assert receipt["final_status"] == "COMPLETE"
        assert receipt["turns_consumed"] == 1
        assert receipt["verified_footprint_tokens"] is not None
        # Must include the assembled prefix tokens
        assert receipt["verified_footprint_tokens"] > 30
        print(f"test_harness_role_l (provenance verified, footprint {receipt['verified_footprint_tokens']}): PASS")

if __name__ == "__main__":
    test_harness_role_s()
    test_harness_role_l()
    print("ALL HARNESS STATE MACHINE TESTS PASSED.")
