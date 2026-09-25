#!/usr/bin/env python3
"""
tests/test_executor_harness.py
Regression tests for tools/executor_harness.py state machine.
Tests mock interaction loops for Role S and Role D, compiler feedback cycles,
and execution receipt emission.
"""

import sys
import os
import tempfile
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools.executor_harness import ExecutionHarness

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS_DIR = os.path.join(ROOT_DIR, "tools")

def test_harness_role_s():
    with tempfile.TemporaryDirectory() as tmp_dir:
        target_file = os.path.join(tmp_dir, "target.lean")
        with open(target_file, "w") as f:
            f.write("theorem frozen_target (n : Nat) : n + 0 = n := by sorry\n")
            
        manifest_file = os.path.join(tmp_dir, "manifest.md")
        with open(manifest_file, "w") as f:
            f.write("Standard Method Mode rules.\n")
            
        out_dir = os.path.join(tmp_dir, "run_s")
        
        # Turn 1: Bad stub (missing liftT)
        # Turn 2: Valid stub
        mock_turn1 = "Here is my attempt:\n```lean\nabbrev LiftDom := Nat\nabbrev LiftCod := Nat × Unit\n```"
        mock_turn2 = """Here is the complete valid stub:
```lean
abbrev LiftDom := Nat
abbrev LiftCod := Nat × Unit

def liftT (n : LiftDom) : LiftCod := (n, ())

def invariant (p : LiftCod) : Nat := p.1

theorem preservation_bridge (m : Nat) : (m + 0 = m) ↔ (invariant (liftT m) + 0 = invariant (liftT m)) := by
  sorry
```"""
        
        harness = ExecutionHarness(
            role="S",
            model_id="claude-sonnet-4-6",
            target_file=target_file,
            manifest_file=manifest_file,
            stub_file=None,
            output_dir=out_dir,
            mock_mode=True,
            mock_responses=[mock_turn1, mock_turn2]
        )
        
        receipt = harness.run()
        assert receipt["status"] == "COMPLETE", f"Expected COMPLETE, got {receipt['status']}"
        assert receipt["turns_completed"] == 2
        assert os.path.exists(os.path.join(out_dir, "execution_receipt.json"))
        assert os.path.exists(os.path.join(out_dir, "conversation_transcript.json"))
        print("test_harness_role_s: PASS (recovered on turn 2, receipt verified)")


def test_harness_role_d():
    with tempfile.TemporaryDirectory() as tmp_dir:
        target_file = os.path.join(tmp_dir, "target.lean")
        with open(target_file, "w") as f:
            f.write("theorem frozen_target (n : Nat) (hn : 2 <= n) : n + 0 = n := by sorry\n")
            
        manifest_file = os.path.join(tmp_dir, "manifest.md")
        with open(manifest_file, "w") as f:
            f.write("Standard Method Mode rules.\n")
            
        out_dir = os.path.join(tmp_dir, "run_d")
        
        # Turn 1: Wrong proof (fails verification)
        mock_turn1 = """```lean
theorem executor_theorem (m : Nat) : m + 1 = 1 + m := by omega
```"""
        # Turn 2: Correct proof with binder renaming
        mock_turn2 = """```lean
theorem executor_theorem (m : Nat) (hm : 2 <= m) : m + 0 = m := by rfl
```"""
        
        harness = ExecutionHarness(
            role="D",
            model_id="claude-sonnet-4-6",
            target_file=target_file,
            manifest_file=manifest_file,
            stub_file=None,
            output_dir=out_dir,
            mock_mode=True,
            mock_responses=[mock_turn1, mock_turn2]
        )
        
        receipt = harness.run()
        assert receipt["status"] == "COMPLETE", f"Expected COMPLETE, got {receipt['status']}"
        assert receipt["turns_completed"] == 2
        assert receipt["footprint_tokens"] is not None
        assert receipt["footprint_tokens"] > 0
        print(f"test_harness_role_d: PASS (footprint: {receipt['footprint_tokens']} tokens)")

if __name__ == "__main__":
    test_harness_role_s()
    test_harness_role_d()
    print("ALL HARNESS STATE MACHINE TESTS PASSED.")
