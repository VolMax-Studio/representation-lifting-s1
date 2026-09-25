#!/usr/bin/env python3
"""
tools/check_bridge.py
Lean-native representation stub and bridge verification harness.
Invokes tools/CheckBridge.lean in the Lean kernel/MetaM environment.
Enforces:
1. Extraction of top-level imports to the head of the file.
2. Lean compilation of the representation stub.
3. Axiom audit on representation layer (no sorryAx, no custom axioms).
4. Identity Guard (AND semantics: LiftDom = LiftCod AND liftT = id).
5. Sequential dependent binder type matching.
6. Target linkage and AST constant reference to liftT.
7. Verification of exact sentinel: CHECK_BRIDGE_SENTINEL_OK.
Part of representation-lifting-s1 experimental protocol.
"""

import sys
import os
import re
import subprocess
import tempfile
import shutil

TOOLS_DIR = os.path.abspath(os.path.dirname(__file__))
CHECK_BRIDGE_LEAN = os.path.join(TOOLS_DIR, "CheckBridge.lean")

SENTINEL = "CHECK_BRIDGE_SENTINEL_OK"

def extract_imports_and_body(text: str) -> tuple[list[str], str]:
    imports = []
    body_lines = []
    for line in text.splitlines():
        if re.match(r'^\s*import\b', line):
            imports.append(line.strip())
        else:
            body_lines.append(line)
    return imports, "\n".join(body_lines)

def verify_bridge_with_lean(target_file: str, stub_file: str) -> tuple[bool, str]:
    lean_bin = shutil.which("lean")
    if not lean_bin:
        raise FileNotFoundError("'lean' required. Pinned Lean toolchain is missing from PATH.")
        
    with open(target_file, "r", encoding="utf-8") as f:
        target_content = f.read()
    with open(stub_file, "r", encoding="utf-8") as f:
        stub_content = f.read()
    with open(CHECK_BRIDGE_LEAN, "r", encoding="utf-8") as f:
        meta_checker_content = f.read()
        
    t_imports, t_body = extract_imports_and_body(target_content)
    s_imports, s_body = extract_imports_and_body(stub_content)
    m_imports, m_body = extract_imports_and_body(meta_checker_content)
    
    # Deduplicate imports while preserving order
    all_imports = ["import Lean"]
    for imp in m_imports + t_imports + s_imports:
        if imp not in all_imports:
            all_imports.append(imp)
            
    with tempfile.TemporaryDirectory() as tmp_dir:
        harness_file = os.path.join(tmp_dir, "CheckBridgeHarness.lean")
        
        with open(harness_file, "w", encoding="utf-8") as f:
            # 1. Imports at the absolute top
            for imp in all_imports:
                f.write(f"{imp}\n")
            f.write("\n-- Meta-checker core\n")
            f.write(m_body)
            f.write("\n\n-- Target statement\n")
            f.write(t_body)
            f.write("\n\n-- Candidate stub\n")
            f.write(s_body)
            f.write("\n\n-- Run verification\n")
            f.write("#eval runCheckBridge `frozen_target `preservation_bridge `liftT `LiftDom `LiftCod\n")
            
        cmd = ["lake", "env", "lean", harness_file] if shutil.which("lake") and os.path.exists("lakefile.toml") else ["lean", harness_file]
        res = subprocess.run(cmd, capture_output=True, text=True)
        
        output = (res.stdout + "\n" + res.stderr).strip()
        
        # Must exit with 0 AND contain exact sentinel line
        if res.returncode == 0 and SENTINEL in output:
            return True, f"BRIDGE_VALID: Structure, Identity Guard, and Target Linkage verified."
        else:
            lines = [line for line in output.splitlines() if "error" in line.lower() or "IDENTITY_GUARD" in line or "UNLINKED" in line or "TAUTOLOGICAL" in line or "BINDER_" in line or "NON_EQUIVALENCE" in line or "FORBIDDEN_" in line]
            err_msg = lines[0] if lines else (output[:200] if output else "Elaboration failure")
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
