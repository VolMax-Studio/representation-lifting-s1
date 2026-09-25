#!/usr/bin/env python3
"""
tools/check_bridge.py
Lean-native representation stub and bridge verification harness in v0.9:
1. Strict requirement for pinned Lake environment (lean-toolchain, lakefile.toml, lake-manifest.json).
2. Defense-in-depth static security scan:
   Rejects escape tokens (sorry, admit, native_decide, axiom), meta-programming commands
   (run_cmd, #eval, initialize, unsafe, elab, macro, syntax), dangerous options (set_option debug.*),
   compiler escape hatches (@[implemented_by]), IO manipulations (IO.FS, IO.Process), and trust core spoofing.
3. Process & Filesystem Sandbox:
   Scrubs secrets from environment, snapshots repository files, enforces integrity check post-compilation.
4. Independent Module Compilation & Kernel Replay:
   - Compiles TrustedTargetModule (contains frozen target statement).
   - Replays TrustedTargetModule through kernel with `lake env leanchecker TrustedTargetModule`.
   - Compiles CandidateSModule (imports TrustedTargetModule, contains candidate stub).
   - Replays CandidateSModule through kernel with `lake env leanchecker CandidateSModule`.
5. Host-side Semantic Verifier (tools/CheckBridge.lean):
   - Strictly evaluates candidate declarations via CandidateSModule module index.
   - Pure representation axiom audit across ALL candidate declarations (zero sorryAx).
   - Identity Guard (AND semantics: LiftDom ≡ LiftCod AND liftT ≡ id).
   - Sequential dependent binder type matching.
   - Target linkage, LiftedClaim linkage, and constant reference to liftT.
   - Method Mode deny-list enforcement across all candidate declarations.
   - Enforces sentinel: CHECK_BRIDGE_SENTINEL_OK.
Part of representation-lifting-s1 experimental protocol (v0.9).
"""

import sys
import os
import re
import json
import subprocess
import shutil

TOOLS_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(TOOLS_DIR, ".."))
CHECK_BRIDGE_LEAN = os.path.join(TOOLS_DIR, "CheckBridge.lean")

SENTINEL = "CHECK_BRIDGE_SENTINEL_OK"

FORBIDDEN_PATTERN = re.compile(
    r'(^|[^a-zA-Z0-9_`])(sorry|admit)([^a-zA-Z0-9_`]|$)|'
    r'native_decide|^\s*axiom\b|^\s*run_cmd\b|^\s*#eval\b|^\s*initialize\b|'
    r'^\s*unsafe\b|^\s*elab\b|^\s*macro\b|^\s*syntax\b|'
    r'set_option\s+debug\.|@\[implemented_by\b|IO\.FS\b|IO\.Process\b|\bVerifierTrustCore\b',
    re.MULTILINE
)

def extract_imports_and_body(text: str) -> tuple[list[str], str]:
    imports = []
    body_lines = []
    for line in text.splitlines():
        if re.match(r'^\s*import\b', line):
            imports.append(line.strip())
        else:
            body_lines.append(line)
    return imports, "\n".join(body_lines)

def take_repo_snapshot() -> dict[str, str]:
    snapshot = {}
    for d in ["tools", "fixtures", "calibration", "admissibility"]:
        dp = os.path.join(PROJECT_ROOT, d)
        if os.path.isdir(dp):
            for root, _, files in os.walk(dp):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        with open(fp, "rb") as fh:
                            import hashlib
                            snapshot[fp] = hashlib.sha256(fh.read()).hexdigest()
                    except Exception:
                        pass
    return snapshot

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

    # 2. Defense-in-depth static security scan
    if re.search(r'^\s*axiom\b', stub_content, re.MULTILINE):
        return False, "VERIFICATION_FAILED: FORBIDDEN_REPRESENTATION_AXIOM: Forbidden custom axiom detected in stub."

    if FORBIDDEN_PATTERN.search(stub_content):
        return False, "FAIL_CLOSED: Forbidden command/meta-programming/escape token detected in stub."

    t_imports, t_body = extract_imports_and_body(target_content)
    s_imports, s_body = extract_imports_and_body(stub_content)

    with open(CHECK_BRIDGE_LEAN, "r", encoding="utf-8") as f:
        meta_checker_content = f.read()
    _, m_body = extract_imports_and_body(meta_checker_content)

    prohibited_list = "[]"
    if admissibility_json and os.path.isfile(admissibility_json):
        with open(admissibility_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        consts = data.get("prohibited_constants", [])
        lean_items = [f"`{c}" for c in consts]
        prohibited_list = "[" + ", ".join(lean_items) + "]"

    tmp_dir = os.path.join(PROJECT_ROOT, f".lake_candidate_build_s_{os.getpid()}")
    os.makedirs(tmp_dir, exist_ok=True)

    try:
        # Snapshot repository state
        repo_snapshot_before = take_repo_snapshot()

        lp_proc = subprocess.run(["lake", "env", "printenv", "LEAN_PATH"], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True)
        base_lp = lp_proc.stdout.strip()
        env = os.environ.copy()
        for k in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GITHUB_TOKEN", "SSH_AUTH_SOCK"]:
            env.pop(k, None)
        env["LEAN_PATH"] = f"{tmp_dir}:{base_lp}"

        # Step A: Build TrustedTargetModule
        target_lean = os.path.join(tmp_dir, "TrustedTargetModule.lean")
        target_olean = os.path.join(tmp_dir, "TrustedTargetModule.olean")
        with open(target_lean, "w", encoding="utf-8") as f:
            for imp in t_imports:
                f.write(f"{imp}\n")
            f.write("\n")
            f.write(t_body)
            f.write("\n")

        res_t = subprocess.run(["lake", "env", "lean", "-o", target_olean, target_lean], cwd=PROJECT_ROOT, env=env, capture_output=True, text=True)
        if res_t.returncode != 0:
            return False, f"TARGET_COMPILATION_FAILED: {res_t.stderr}"

        res_tc = subprocess.run(["lake", "env", "leanchecker", "TrustedTargetModule"], cwd=PROJECT_ROOT, env=env, capture_output=True, text=True)
        if res_tc.returncode != 0:
            return False, f"TARGET_KERNEL_REPLAY_FAILED: {res_tc.stderr}"

        # Step B: Build CandidateSModule
        cand_lean = os.path.join(tmp_dir, "CandidateSModule.lean")
        cand_olean = os.path.join(tmp_dir, "CandidateSModule.olean")
        with open(cand_lean, "w", encoding="utf-8") as f:
            f.write("import TrustedTargetModule\n")
            for imp in s_imports:
                f.write(f"{imp}\n")
            f.write("\nnamespace CandidateExecutor\n")
            f.write(s_body)
            f.write("\nend CandidateExecutor\n")

        res_c = subprocess.run(["lake", "env", "lean", "-o", cand_olean, cand_lean], cwd=PROJECT_ROOT, env=env, capture_output=True, text=True)
        if res_c.returncode != 0:
            return False, f"VERIFICATION_FAILED: Candidate stub failed to elaborate: {res_c.stderr or res_c.stdout}"

        # Filesystem integrity check
        repo_snapshot_after = take_repo_snapshot()
        if repo_snapshot_before != repo_snapshot_after:
            return False, "FAIL_CLOSED: Unauthorized filesystem mutation detected during candidate compilation."

        res_cc = subprocess.run(["lake", "env", "leanchecker", "CandidateSModule"], cwd=PROJECT_ROOT, env=env, capture_output=True, text=True)
        if res_cc.returncode != 0:
            return False, f"FAIL_CLOSED: Candidate module failed kernel replay via leanchecker: {res_cc.stderr}"

        # Step C: Host-side Semantic Verifier
        ver_lean = os.path.join(tmp_dir, "VerifierSModule.lean")
        with open(ver_lean, "w", encoding="utf-8") as f:
            f.write("import Lean\n")
            f.write("import TrustedTargetModule\n")
            f.write("import CandidateSModule\n\n")
            f.write(m_body)
            f.write("\n\n")
            f.write(f"#eval! VerifierTrustCore.runCheckBridge `CandidateSModule `frozen_target {prohibited_list}\n")

        res_v = subprocess.run(["lake", "env", "lean", ver_lean], cwd=PROJECT_ROOT, env=env, capture_output=True, text=True)
        output = (res_v.stdout + "\n" + res_v.stderr).strip()

        if res_v.returncode == 0 and SENTINEL in output:
            return True, "BRIDGE_VALID: Structure, Identity Guard, and LiftedClaim Linkage verified."
        else:
            lines = [line for line in output.splitlines() if "error" in line.lower() or "IDENTITY_GUARD" in line or "TAUTOLOGICAL" in line or "BINDER_" in line or "BRIDGE_" in line or "FORBIDDEN_" in line]
            err_msg = lines[0] if lines else (output[:200] if output else "Elaboration failure")
            return False, f"VERIFICATION_FAILED: {err_msg}"

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

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
