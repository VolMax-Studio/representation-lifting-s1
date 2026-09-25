#!/usr/bin/env python3
"""
tools/executor_harness.py
Cryptographic execution harness for representation-lifting-s1.
Standardizes the agent tool loop across roles:
- Role S (Representation Search Executor): 3600s wall-clock, max 15 turns
- Role D (Direct Proof Executor): 10800s wall-clock, max 30 turns
- Role L (Lifted Proof Executor): 10800s wall-clock, max 30 turns

Governs tool execution:
- Compiler invocation: `lake env lean <candidate_file>`
- Bridge validation: `tools/check_bridge.py`
- Proof verification: `tools/verify_proof.sh`
Outputs a cryptographically locked run receipt.
Part of representation-lifting-s1 experimental protocol.
"""

import sys
import os
import json
import time
import hashlib
import subprocess
from datetime import datetime, timezone

ROLE_BUDGETS = {
    "S": {"max_wallclock_seconds": 3600, "max_turns": 15},
    "D": {"max_wallclock_seconds": 10800, "max_turns": 30},
    "L": {"max_wallclock_seconds": 10800, "max_turns": 30}
}

def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def compile_lean_file(file_path: str) -> tuple[int, str]:
    """Invokes the pinned Lean compiler on candidate file."""
    cmd = ["lake", "env", "lean", file_path] if os.path.exists("lakefile.toml") else ["lean", file_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    output = (res.stdout + "\n" + res.stderr).strip()
    return res.returncode, output

def main():
    if len(sys.argv) < 5:
        print(f"Usage: {sys.argv[0]} <role:S|D|L> <model_id> <target_file> <manifest_file> [stub_file]", file=sys.stderr)
        sys.exit(1)
        
    role = sys.argv[1].upper()
    if role not in ROLE_BUDGETS:
        print(f"Error: Invalid role '{role}'. Must be one of S, D, L.", file=sys.stderr)
        sys.exit(1)
        
    model_id = sys.argv[2]
    target_file = sys.argv[3]
    manifest_file = sys.argv[4]
    stub_file = sys.argv[5] if len(sys.argv) > 5 else None
    
    if role == "L" and not stub_file:
        print("Error: Role L requires a frozen stub file.", file=sys.stderr)
        sys.exit(1)
        
    budget = ROLE_BUDGETS[role]
    
    context_hashes = {
        "target_file": target_file,
        "target_sha256": compute_sha256(target_file),
        "manifest_file": manifest_file,
        "manifest_sha256": compute_sha256(manifest_file),
    }
    if stub_file:
        context_hashes["stub_file"] = stub_file
        context_hashes["stub_sha256"] = compute_sha256(stub_file)
        
    start_time_utc = datetime.now(timezone.utc).isoformat()
    start_clock = time.perf_counter()
    
    print(f"Harness Initialized for Role {role}")
    print(f"  Model ID: {model_id}")
    print(f"  Max Wall-clock: {budget['max_wallclock_seconds']}s")
    print(f"  Max Turns: {budget['max_turns']}")
    print(f"  Context Hashes: {json.dumps(context_hashes, indent=2)}")

if __name__ == "__main__":
    main()
