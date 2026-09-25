#!/usr/bin/env python3
"""
tools/check_bridge.py
Lean-native representation stub and bridge verification harness.
Invokes tools/CheckBridge.lean in the Lean kernel/MetaM environment to verify:
1. Compilation of the representation stub.
2. Definitional triviality check (Identity Guard: LiftDom = LiftCod or liftT = id).
3. Target linkage verification (forallTelescope, Iff conclusion, syntactic tautology check,
   and AST constant reference to liftT).
4. Strict sorry audit (sorryAx permitted ONLY in preservation_bridge).
Part of representation-lifting-s1 experimental protocol.
"""

import sys
import os
import subprocess
import tempfile
import shutil

TOOLS_DIR = os.path.abspath(os.path.dirname(__file__))
CHECK_BRIDGE_LEAN = os.path.join(TOOLS_DIR, "CheckBridge.lean")

def verify_bridge_with_lean(target_file: str, stub_file: str) -> tuple[bool, str]:
    # Check that lean compiler is installed
    lean_bin = shutil.which("lean")
    if not lean_bin:
        return False, "TOOLCHAIN_ERROR: 'lean' binary not found on PATH. Pinned Lean toolchain is required."
        
    with open(target_file, "r", encoding="utf-8") as f:
        target_content = f.read()
    with open(stub_file, "r", encoding="utf-8") as f:
        stub_content = f.read()
    with open(CHECK_BRIDGE_LEAN, "r", encoding="utf-8") as f:
        meta_checker_content = f.read()
        
    with tempfile.TemporaryDirectory() as tmp_dir:
        harness_file = os.path.join(tmp_dir, "CheckBridgeHarness.lean")
        
        # Build unified verification harness
        with open(harness_file, "w", encoding="utf-8") as f:
            f.write("import Lean\n\n")
            f.write("-- Meta-checker definitions\n")
            f.write(meta_checker_content)
            f.write("\n\n-- Target statement\n")
            f.write(target_content)
            f.write("\n\n-- Candidate stub\n")
            f.write(stub_content)
            f.write("\n\n-- Execute verification\n")
            f.write("#eval runCheckBridge `frozen_target `preservation_bridge `liftT `LiftDom `LiftCod\n")
            
        # Execute lean
        # If lake is available and project is a lake package, use 'lake env lean', otherwise 'lean'
        cmd = ["lake", "env", "lean", harness_file] if shutil.which("lake") else ["lean", harness_file]
        res = subprocess.run(cmd, capture_output=True, text=True)
        
        output = (res.stdout + "\n" + res.stderr).strip()
        
        if res.returncode == 0 and "BRIDGE_VALID" in output:
            return True, "BRIDGE_VALID: Structure, Identity Guard, and Target Linkage verified."
        else:
            # Extract first meaningful error line
            lines = [line for line in output.splitlines() if "error" in line.lower() or "IDENTITY_GUARD" in line or "UNLINKED" in line or "TAUTOLOGICAL" in line or "EXTRA_HYPOTHESIS" in line or "NON_EQUIVALENCE" in line]
            err_msg = lines[0] if lines else (output[:200] if output else "Unknown elaboration failure")
            return False, f"VERIFICATION_FAILED: {err_msg}"

check_bridge = verify_bridge_with_lean

def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <target_stmt_file> <stub_file>", file=sys.stderr)
        sys.exit(1)
        
    target_file = sys.argv[1]
    stub_file = sys.argv[2]
    
    valid, message = verify_bridge_with_lean(target_file, stub_file)
    if valid:
        print(f"PASS: {message}")
        sys.exit(0)
    else:
        print(f"FAIL: {message}")
        sys.exit(1)

if __name__ == "__main__":
    main()
