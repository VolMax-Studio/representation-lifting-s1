#!/usr/bin/env python3
"""
tools/check_bridge.py
Lean-native representation stub and bridge verification harness.
Invokes tools/CheckBridge.lean in the pinned Lake/Lean kernel environment.
Enforces:
1. Strict requirement for pinned Lake environment (lean-toolchain, lakefile.toml, lake-manifest.json).
2. Extraction of top-level imports to the head of the file.
3. Elaboration and pure-kernel axiom audit of LiftedClaim and BridgeProp (zero sorryAx).
4. Identity Guard (AND semantics: LiftDom = LiftCod AND liftT = id).
5. Sequential dependent binder type matching.
6. Target linkage, LiftedClaim linkage, and constant reference to liftT.
7. Machine-readable Method Mode deny-list enforcement.
8. Verification of exact sentinel: CHECK_BRIDGE_SENTINEL_OK.
Part of representation-lifting-s1 experimental protocol (v0.6).
"""

import sys
import os
import re
import json
import subprocess
import tempfile
import shutil

TOOLS_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(TOOLS_DIR, ".."))
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

def verify_bridge_with_lean(target_file: str, stub_file: str, admissibility_json: str | None = None) -> tuple[bool, str]:
    # 1. Strict environment audit: Require pinned Lake project
    req_files = ["lean-toolchain", "lakefile.toml", "lake-manifest.json"]
    for rf in req_files:
        if not os.path.isfile(os.path.join(PROJECT_ROOT, rf)):
            return False, f"ENVIRONMENT_INVALID: Required pinned file '{rf}' missing in {PROJECT_ROOT}."

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
            
    # Prohibited constants list for Lean
    prohibited_list = "[]"
    if admissibility_json and os.path.isfile(admissibility_json):
        with open(admissibility_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        consts = data.get("prohibited_constants", [])
        lean_items = [f"`{c}" for c in consts]
        prohibited_list = "[" + ", ".join(lean_items) + "]"

    with tempfile.TemporaryDirectory() as tmp_dir:
        harness_file = os.path.join(tmp_dir, "CheckBridgeHarness.lean")
        
        with open(harness_file, "w", encoding="utf-8") as f:
            for imp in all_imports:
                f.write(f"{imp}\n")
            f.write("\n-- Meta-checker core\n")
            f.write(m_body)
            f.write("\n\n-- Target statement\n")
            f.write(t_body)
            f.write("\n\n-- Candidate stub\n")
            f.write(s_body)
            f.write("\n\n-- Run verification\n")
            f.write(f"#eval runCheckBridge `frozen_target `BridgeProp `LiftedClaim `liftT `LiftDom `LiftCod {prohibited_list}\n")
            
        cmd = ["lake", "env", "lean", harness_file]
        res = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
        
        output = (res.stdout + "\n" + res.stderr).strip()
        
        if res.returncode == 0 and SENTINEL in output:
            return True, f"BRIDGE_VALID: Structure, Identity Guard, and LiftedClaim Linkage verified."
        else:
            lines = [line for line in output.splitlines() if "error" in line.lower() or "IDENTITY_GUARD" in line or "UNLINKED" in line or "TAUTOLOGICAL" in line or "BINDER_" in line or "CLAIM_" in line or "FORBIDDEN_" in line]
            err_msg = lines[0] if lines else (output[:200] if output else "Elaboration failure")
            return False, f"VERIFICATION_FAILED: {err_msg}"

check_bridge = verify_bridge_with_lean

def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <target_stmt_file> <stub_file> [admissibility_json]", file=sys.stderr)
        sys.exit(1)
        
    target_file = sys.argv[1]
    stub_file = sys.argv[2]
    admissibility_json = sys.argv[3] if len(sys.argv) > 3 else None
    
    valid, message = verify_bridge_with_lean(target_file, stub_file, admissibility_json)
    print(message)
    sys.exit(0 if valid else 1)

if __name__ == "__main__":
    main()
