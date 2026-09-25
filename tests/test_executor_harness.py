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
            last_msg = msgs[-1]["content"] if msgs else ""
            if "FROZEN REPRESENTATION CORE" in last_msg or "Define new `LiftedClaim` and `BridgeProp`" in last_msg:
                return ("""```lean
def LiftedClaim : Prop := liftT 0 = 1
def BridgeProp : Prop := True ↔ (liftT 0 = 1)
```""", "end_turn", False)
            return ("""```lean
abbrev LiftDom := Nat
abbrev LiftCod := Nat
def liftT (n : LiftDom) : LiftCod := n + 1
def LiftedClaim : Prop := liftT 0 = 1
def BridgeProp : Prop := True ↔ (liftT 0 = 1)
```""", "end_turn", False)
        elif role == "L":
            return ("""```lean
theorem preservation_bridge : BridgeProp := Iff.intro (fun _ => rfl) (fun _ => trivial)
theorem lifted_theorem : LiftedClaim := rfl
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
        orig_tools = eh.TOOLS_DIR
        try:
            eh.ROOT_DIR = tmp_dir
            eh.TOOLS_DIR = os.path.join(tmp_dir, "tools")
            os.makedirs(eh.TOOLS_DIR, exist_ok=True)
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
            assert report["schema_version"] == "representation-lifting-execution-receipt/v1"
            assert report["direct"]["delta_d_2"] is not None
            assert report["lifted"]["delta_l_2"] is not None
            print("test_harness_calibration (H1 calibration state machine execution): PASS")
        finally:
            eh.ROOT_DIR = orig_root
            eh.TOOLS_DIR = orig_tools

def test_branch_output_non_persistence_isolation():
    """
    Asserts procedural branch-output non-persistence isolation (v0.11):
    1. D proof and receipt exist exclusively in harness process memory during evaluation.
    2. Between completion of D branch and start of S/L branch, no D receipt exists on disk.
    3. No D candidate source, temp module, or log exists on disk.
    4. No persistent file in the working directory contains D's verified proof code (canary secret).
    5. The joint paired receipt is created atomically only after both branches conclude.
    """
    CANARY_SECRET = "CANARY_SECRET_D_PROOF_NONCE_849204820_ISOLATION_CHECK"

    def mock_calib_canary(role, turn, msgs):
        if role == "D":
            return (f"```lean\n-- {CANARY_SECRET}\ntheorem executor_theorem : True := trivial\n```", "end_turn", False)
        elif role == "S":
            last_msg = msgs[-1]["content"] if msgs else ""
            if "FROZEN REPRESENTATION CORE" in last_msg or "Define new `LiftedClaim` and `BridgeProp`" in last_msg:
                return ("""```lean
def LiftedClaim : Prop := liftT 0 = 1
def BridgeProp : Prop := True ↔ (liftT 0 = 1)
```""", "end_turn", False)
            return ("""```lean
abbrev LiftDom := Nat
abbrev LiftCod := Nat
def liftT (n : LiftDom) : LiftCod := n + 1
def LiftedClaim : Prop := liftT 0 = 1
def BridgeProp : Prop := True ↔ (liftT 0 = 1)
```""", "end_turn", False)
        elif role == "L":
            return ("""```lean
theorem preservation_bridge : BridgeProp := Iff.intro (fun _ => rfl) (fun _ => trivial)
theorem lifted_theorem : LiftedClaim := rfl
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
        orig_tools = eh.TOOLS_DIR
        try:
            eh.ROOT_DIR = tmp_dir
            eh.TOOLS_DIR = os.path.join(tmp_dir, "tools")
            os.makedirs(eh.TOOLS_DIR, exist_ok=True)

            calib_dir = os.path.join(tmp_dir, "calibration")
            os.makedirs(calib_dir, exist_ok=True)
            import shutil
            shutil.copy(t1, os.path.join(calib_dir, "mockfam_t1.lean"))
            shutil.copy(t2, os.path.join(calib_dir, "mockfam_t2.lean"))
            adm_dir = os.path.join(tmp_dir, "admissibility")
            os.makedirs(adm_dir, exist_ok=True)
            with open(os.path.join(adm_dir, "mockfam.json"), "w") as f:
                json.dump({"prohibited_constants": []}, f)

            callback_invoked = False

            def verify_d_isolation_hook(calib_report_state):
                nonlocal callback_invoked
                callback_invoked = True

                # 1. No D receipt on disk
                d_receipt_file = os.path.join(eh.TOOLS_DIR, "execution_receipt_d.json")
                assert not os.path.exists(d_receipt_file), f"LEAK: D receipt found on disk at {d_receipt_file}"

                # 2. No joint receipt on disk before L finishes
                joint_receipt_file = os.path.join(eh.TOOLS_DIR, "execution_receipt_calibration_mockfam.json")
                assert not os.path.exists(joint_receipt_file), f"LEAK: Joint receipt created prematurely at {joint_receipt_file}"

                # 3. D results exist strictly in memory
                assert calib_report_state["direct"]["d1_status"] == "COMPLETE"
                assert calib_report_state["direct"]["d2_status"] == "COMPLETE"
                assert calib_report_state["direct"]["w_d_t1"] is not None

                # 4. Canary secret must not exist in ANY file in tmp_dir
                for root, dirs, files in os.walk(tmp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                        except (OSError, UnicodeError):
                            continue
                        assert CANARY_SECRET not in content, f"LEAK: D canary secret found on disk in {file_path}"

            run_tmp_root = os.path.join(tmp_dir, "run_tmp")
            os.makedirs(run_tmp_root, exist_ok=True)
            report = run_calibration_family("mockfam", "claude-sonnet-4-6",
                                            mock_generator=mock_calib_canary,
                                            on_d_complete_callback=verify_d_isolation_hook,
                                            run_tmp_root=run_tmp_root)

            assert callback_invoked is True, "Isolation hook was not invoked between D and S/L"

            # 5. Joint receipt is created after both branches finish
            joint_receipt_file = os.path.join(eh.TOOLS_DIR, "execution_receipt_calibration_mockfam.json")
            assert os.path.exists(joint_receipt_file), "Joint receipt was not created after completion"
            assert report["schema_version"] == "representation-lifting-execution-receipt/v1"
            assert report["direct"]["delta_d_2"] is not None
            assert report["lifted"]["delta_l_2"] is not None
            assert report["direct"]["d1_status"] == "COMPLETE"
            assert report["lifted"]["l1_status"] == "COMPLETE"
            print("test_branch_output_non_persistence_isolation: PASS (D output held strictly in memory, 0 disk leakage)")
        finally:
            eh.ROOT_DIR = orig_root
            eh.TOOLS_DIR = orig_tools

def test_blind_case_branch_isolation_and_governance():
    """
    Tests blind case orchestrator (run_blind_case) under H2 governance:
    1. D executes first, result held strictly in memory (0 disk receipt).
    2. Zero canary leakage across repo tree and run_tmp_root on inter-branch boundary.
    3. S valid -> L executes with S stub -> joint receipt created atomically.
    4. S invalid -> classified as LIFT_NOT_FOUND, L skipped, no resampling.
    """
    from tools.executor_harness import run_blind_case

    CANARY_BLIND = "CANARY_SECRET_BLIND_D_PROOF_998877"

    # Case A: S succeeds -> L executes -> LIFTED_PROVEN
    def mock_blind_success(role, turn, msgs):
        if role == "D":
            return (f"```lean\n-- {CANARY_BLIND}\ntheorem executor_theorem : True := trivial\n```", "end_turn", False)
        elif role == "S":
            return ("""```lean
abbrev LiftDom := Nat
abbrev LiftCod := Nat
def liftT (n : LiftDom) : LiftCod := n + 1
def LiftedClaim : Prop := liftT 0 = 1
def BridgeProp : Prop := True ↔ (liftT 0 = 1)
```""", "end_turn", False)
        elif role == "L":
            return ("""```lean
theorem preservation_bridge : BridgeProp := Iff.intro (fun _ => rfl) (fun _ => trivial)
theorem lifted_theorem : LiftedClaim := rfl
```""", "end_turn", False)
        return ("", "end_turn", True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        target = os.path.join(tmp_dir, "target.lean")
        with open(target, "w") as f:
            f.write("theorem frozen_target : True := by sorry\n")

        import tools.executor_harness as eh
        orig_root = eh.ROOT_DIR
        orig_tools = eh.TOOLS_DIR
        try:
            eh.ROOT_DIR = tmp_dir
            eh.TOOLS_DIR = os.path.join(tmp_dir, "tools")
            os.makedirs(eh.TOOLS_DIR, exist_ok=True)
            adm_dir = os.path.join(tmp_dir, "admissibility")
            os.makedirs(adm_dir, exist_ok=True)
            with open(os.path.join(adm_dir, "default.json"), "w") as f:
                json.dump({"prohibited_constants": []}, f)
            run_tmp = os.path.join(tmp_dir, "run_tmp")
            os.makedirs(run_tmp, exist_ok=True)

            callback_invoked = False
            def verify_blind_d_isolation(blind_report_state):
                nonlocal callback_invoked
                callback_invoked = True
                # 1. No D receipt on disk
                assert not os.path.exists(os.path.join(eh.TOOLS_DIR, "execution_receipt_d.json"))
                # 2. No joint receipt prematurely
                assert not os.path.exists(os.path.join(eh.TOOLS_DIR, "execution_receipt_blind_case01.json"))
                # 3. D exists strictly in memory
                assert blind_report_state["direct"]["final_status"] == "COMPLETE"
                # 4. Zero canary leakage across tmp_dir
                for root, dirs, files in os.walk(tmp_dir):
                    for file in files:
                        fp = os.path.join(root, file)
                        try:
                            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                                c = f.read()
                        except (OSError, UnicodeError):
                            continue
                        assert CANARY_BLIND not in c, f"LEAK: Blind D canary found in {fp}"

            report_a = run_blind_case("case01", target, "claude-sonnet-4-6",
                                      mock_generator=mock_blind_success,
                                      on_d_complete_callback=verify_blind_d_isolation,
                                      run_tmp_root=run_tmp)
            assert callback_invoked is True
            assert report_a["outcome"] == "LIFTED_PROVEN"
            assert report_a["representation_search"]["final_status"] == "COMPLETE"
            assert report_a["lifted"]["final_status"] == "COMPLETE"
            assert os.path.exists(os.path.join(eh.TOOLS_DIR, "execution_receipt_blind_case01.json"))
            print("test_blind_case_branch_isolation_and_governance (success path): PASS")

            # Case B: S fails -> classified LIFT_NOT_FOUND, L skipped, no resampling
            def mock_blind_s_fails(role, turn, msgs):
                if role == "D":
                    return ("```lean\ntheorem executor_theorem : True := trivial\n```", "end_turn", False)
                elif role == "S":
                    return ("invalid stub without lean block", "end_turn", False)
                return ("", "end_turn", True)

            report_b = run_blind_case("case02", target, "claude-sonnet-4-6",
                                      mock_generator=mock_blind_s_fails,
                                      run_tmp_root=run_tmp)
            assert report_b["outcome"] == "LIFT_NOT_FOUND"
            assert report_b["representation_search"]["final_status"] == "LIFT_NOT_FOUND"
            assert report_b["lifted"]["final_status"] == "SKIPPED_LIFT_NOT_FOUND"
            assert os.path.exists(os.path.join(eh.TOOLS_DIR, "execution_receipt_blind_case02.json"))
            print("test_blind_case_branch_isolation_and_governance (LIFT_NOT_FOUND path): PASS")
        finally:
            eh.ROOT_DIR = orig_root
            eh.TOOLS_DIR = orig_tools

def test_control_case_execution_and_isolation():
    """
    Tests Negative Control driver (run_control_case) under H0 governance:
    1. D executes on target, result held in memory (0 disk receipt).
    2. Zero canary leakage on inter-branch boundary.
    3. L executes with pre-frozen stub without executing Role S.
    4. Joint receipt execution_receipt_control.json created atomically.
    """
    from tools.executor_harness import run_control_case

    CANARY_CONTROL = "CANARY_CONTROL_SECRET_D_771122"

    def mock_control_gen(role, turn, msgs):
        if role == "D":
            return (f"```lean\n-- {CANARY_CONTROL}\ntheorem executor_theorem : True := trivial\n```", "end_turn", False)
        elif role == "L":
            return ("""```lean
theorem preservation_bridge : BridgeProp := Iff.intro (fun _ => rfl) (fun _ => trivial)
theorem lifted_theorem : LiftedClaim := rfl
```""", "end_turn", False)
        return ("", "end_turn", True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        target = os.path.join(tmp_dir, "control_target.lean")
        stub = os.path.join(tmp_dir, "ControlStub.lean")
        with open(target, "w") as f:
            f.write("theorem frozen_target : True := by sorry\n")
        with open(stub, "w") as f:
            f.write("""
abbrev LiftDom := Nat
abbrev LiftCod := Nat
def liftT (n : LiftDom) : LiftCod := n + 1
def LiftedClaim : Prop := liftT 0 = 1
def BridgeProp : Prop := True ↔ (liftT 0 = 1)
""")

        import tools.executor_harness as eh
        orig_root = eh.ROOT_DIR
        orig_tools = eh.TOOLS_DIR
        try:
            eh.ROOT_DIR = tmp_dir
            eh.TOOLS_DIR = os.path.join(tmp_dir, "tools")
            os.makedirs(eh.TOOLS_DIR, exist_ok=True)
            adm_dir = os.path.join(tmp_dir, "admissibility")
            os.makedirs(adm_dir, exist_ok=True)
            with open(os.path.join(adm_dir, "default.json"), "w") as f:
                json.dump({"prohibited_constants": []}, f)
            run_tmp = os.path.join(tmp_dir, "run_tmp")
            os.makedirs(run_tmp, exist_ok=True)

            callback_invoked = False
            def verify_control_d_isolation(report_state):
                nonlocal callback_invoked
                callback_invoked = True
                # 1. No D receipt on disk
                assert not os.path.exists(os.path.join(eh.TOOLS_DIR, "execution_receipt_d.json"))
                # 2. No control receipt prematurely
                assert not os.path.exists(os.path.join(eh.TOOLS_DIR, "execution_receipt_control.json"))
                # 3. D exists in memory
                assert report_state["direct"]["final_status"] == "COMPLETE"
                # 4. Zero canary leakage across tmp_dir
                for root, dirs, files in os.walk(tmp_dir):
                    for file in files:
                        fp = os.path.join(root, file)
                        try:
                            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                                c = f.read()
                        except (OSError, UnicodeError):
                            continue
                        assert CANARY_CONTROL not in c, f"LEAK: Control D canary found in {fp}"

            report = run_control_case(
                "claude-sonnet-4-6",
                target_path=target,
                stub_path=stub,
                mock_generator=mock_control_gen,
                on_d_complete_callback=verify_control_d_isolation,
                run_tmp_root=run_tmp
            )

            assert callback_invoked is True
            assert report["direct"]["final_status"] == "COMPLETE"
            assert report["lifted"]["final_status"] == "COMPLETE"
            assert os.path.exists(os.path.join(eh.TOOLS_DIR, "execution_receipt_control.json"))
            print("test_control_case_execution_and_isolation: PASS")
        finally:
            eh.ROOT_DIR = orig_root
            eh.TOOLS_DIR = orig_tools

if __name__ == "__main__":
    test_harness_role_s()
    test_harness_role_l()
    test_harness_truncation()
    test_harness_calibration()
    test_branch_output_non_persistence_isolation()
    test_blind_case_branch_isolation_and_governance()
    test_control_case_execution_and_isolation()
    print("ALL HARNESS STATE MACHINE TESTS PASSED.")
