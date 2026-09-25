#!/usr/bin/env bash
# tools/verify_lifted.sh
# Verification harness for Role L (Lifted Proof Executor) in v0.9:
# 1. Enforces pinned Lake environment (lean-toolchain, lakefile.toml, lake-manifest.json).
# 2. Defense-in-depth static security scan:
#    Rejects escape tokens (sorry, admit, native_decide, axiom), meta-programming commands
#    (run_cmd, #eval, initialize, unsafe, elab, macro, syntax), dangerous options (set_option debug.*),
#    compiler escape hatches (@[implemented_by]), IO manipulations (IO.FS, IO.Process), and trust core spoofing.
# 3. Process & Filesystem Sandbox:
#    Scrubs secrets from environment, snapshots repository files, enforces integrity check post-compilation.
# 4. Independent Module Compilation & Kernel Replay:
#    - Compiles TrustedTargetModule (contains frozen target statement).
#    - Replays TrustedTargetModule through kernel with `lake env leanchecker TrustedTargetModule`.
#    - Compiles FrozenSpecModule (imports TrustedTargetModule, contains frozen representation & BridgeProp).
#    - Replays FrozenSpecModule through kernel with `lake env leanchecker FrozenSpecModule`.
#    - Compiles CandidateLModule (imports FrozenSpecModule, contains candidate lifted proof & bridge).
#    - Replays CandidateLModule through kernel with `lake env leanchecker CandidateLModule`.
# 5. Host-side Semantic Verifier (tools/VerifyLifted.lean):
#    - Strictly evaluates candidate declarations via CandidateLModule module index.
#    - Verifies type(preservation_bridge) ≡ BridgeProp and type(lifted_theorem) ≡ LiftedClaim.
#    - Strict kernel axiom audit on both declarations.
#    - Transitive non-circularity audit strictly within CandidateLModule.
#    - Method Mode Deny-List enforcement across all candidate declarations.
#    - Mechanical synthesis of target theorem with kernel axiom audit.
#    - Enforces sentinel: VERIFY_LIFTED_SENTINEL_OK.
# Part of representation-lifting-s1 experimental protocol (v0.9).

set -euo pipefail

if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <frozen_target_file> <frozen_stub_prefix_file> <executor_lean_file> [admissibility_json]" >&2
    exit 2
fi

FROZEN_TARGET_FILE="$1"
FROZEN_STUB_PREFIX="$2"
EXECUTOR_LEAN_FILE="$3"
ADMISSIBILITY_JSON="${4:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 1. Strict environment audit: Require pinned Lake project
if [ ! -f "$PROJECT_ROOT/lean-toolchain" ] || [ ! -f "$PROJECT_ROOT/lakefile.toml" ] || [ ! -f "$PROJECT_ROOT/lake-manifest.json" ]; then
    echo "ENVIRONMENT_INVALID: Pinned Lake project missing or incomplete in $PROJECT_ROOT." >&2
    exit 2
fi

# 2. Defense-in-depth static security scan
FORBIDDEN_PATTERN='(^|[^[:alnum:]_`])(sorry|admit)([^[:alnum:]_`]|$)|native_decide|^[[:space:]]*axiom\b|^[[:space:]]*run_cmd\b|^[[:space:]]*#eval\b|^[[:space:]]*initialize\b|^[[:space:]]*unsafe\b|^[[:space:]]*elab\b|^[[:space:]]*macro\b|^[[:space:]]*syntax\b|set_option[[:space:]]+debug\.|@\[implemented_by\b|IO\.FS\b|IO\.Process\b|\bVerifierTrustCore\b'
if grep -En "$FORBIDDEN_PATTERN" "$EXECUTOR_LEAN_FILE" >/dev/null 2>&1; then
    echo "FAIL_CLOSED: Forbidden command/meta-programming/escape token detected in $EXECUTOR_LEAN_FILE" >&2
    exit 1
fi

TMP_DIR="$(pwd)/.lake_candidate_build_$$"
mkdir -p "$TMP_DIR"
trap 'rm -rf "$TMP_DIR"' EXIT

# 3. Snapshot repository state for filesystem mutation detection
REPO_SNAPSHOT_BEFORE="$(find tools fixtures calibration admissibility -type f -exec sha256sum {} + | sort)"

# 4. Parse prohibited constants from admissibility JSON
PROHIBITED_LEAN_LIST="[]"
if [ -n "$ADMISSIBILITY_JSON" ] && [ -f "$ADMISSIBILITY_JSON" ]; then
    PROHIBITED_LEAN_LIST=$(python3 -c '
import sys, json
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
consts = data.get("prohibited_constants", [])
lean_items = [f"`{c}" for c in consts]
print("[" + ", ".join(lean_items) + "]")
' "$ADMISSIBILITY_JSON")
fi

# Helper to extract imports
EXTRACT_IMPORTS='
import sys, re
paths = sys.argv[1:]
imports = []
for p in paths:
    if p and p != "":
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                if re.match(r"^\s*import\b", line):
                    imp = line.strip()
                    if imp not in imports:
                        imports.append(imp)
for imp in imports:
    print(imp)
'

# Step A: Build TrustedTargetModule
TARGET_IMPORTS=$(python3 -c "$EXTRACT_IMPORTS" "$FROZEN_TARGET_FILE")
{
    echo "$TARGET_IMPORTS"
    echo ""
    grep -vE '^\s*import\b' "$FROZEN_TARGET_FILE"
} > "$TMP_DIR/TrustedTargetModule.lean"

LP="$(lake env printenv LEAN_PATH)"
export LEAN_PATH="$TMP_DIR:$LP"

if ! lake env lean -o "$TMP_DIR/TrustedTargetModule.olean" "$TMP_DIR/TrustedTargetModule.lean" > "$TMP_DIR/target_comp.log" 2>&1; then
    echo "TARGET_COMPILATION_FAILED:" >&2
    cat "$TMP_DIR/target_comp.log" >&2
    exit 1
fi
lake env leanchecker TrustedTargetModule >/dev/null 2>&1 || {
    echo "TARGET_KERNEL_REPLAY_FAILED: Trusted target failed leanchecker." >&2
    exit 1
}

# Step B: Build FrozenSpecModule
SPEC_IMPORTS=$(python3 -c "$EXTRACT_IMPORTS" "$FROZEN_STUB_PREFIX")
{
    echo "import TrustedTargetModule"
    echo "$SPEC_IMPORTS"
    echo ""
    grep -vE '^\s*import\b' "$FROZEN_STUB_PREFIX"
} > "$TMP_DIR/FrozenSpecModule.lean"

if ! lake env lean -o "$TMP_DIR/FrozenSpecModule.olean" "$TMP_DIR/FrozenSpecModule.lean" > "$TMP_DIR/spec_comp.log" 2>&1; then
    echo "SPEC_COMPILATION_FAILED:" >&2
    cat "$TMP_DIR/spec_comp.log" >&2
    exit 1
fi
lake env leanchecker FrozenSpecModule >/dev/null 2>&1 || {
    echo "SPEC_KERNEL_REPLAY_FAILED: Frozen spec failed leanchecker." >&2
    exit 1
}

# Step C: Build CandidateLModule
CAND_IMPORTS=$(python3 -c "$EXTRACT_IMPORTS" "$EXECUTOR_LEAN_FILE")
{
    echo "import FrozenSpecModule"
    echo "$CAND_IMPORTS"
    echo ""
    echo "namespace CandidateExecutor"
    grep -vE '^\s*import\b' "$EXECUTOR_LEAN_FILE"
    echo "end CandidateExecutor"
} > "$TMP_DIR/CandidateLModule.lean"

# Scrub secrets and execute candidate compilation
env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u GEMINI_API_KEY -u GITHUB_TOKEN -u SSH_AUTH_SOCK \
    lake env lean -o "$TMP_DIR/CandidateLModule.olean" "$TMP_DIR/CandidateLModule.lean" > "$TMP_DIR/cand_comp.log" 2>&1 || {
    echo "VERIFY_LIFTED_FAILED: Candidate code failed to elaborate:" >&2
    cat "$TMP_DIR/cand_comp.log" >&2
    exit 1
}

# Filesystem mutation integrity guard
REPO_SNAPSHOT_AFTER="$(find tools fixtures calibration admissibility -type f -exec sha256sum {} + | sort)"
if [ "$REPO_SNAPSHOT_BEFORE" != "$REPO_SNAPSHOT_AFTER" ]; then
    echo "FAIL_CLOSED: Unauthorized filesystem mutation detected during candidate compilation." >&2
    exit 1
fi

# Kernel replay on candidate module via leanchecker
if ! lake env leanchecker CandidateLModule > "$TMP_DIR/leanchecker.log" 2>&1; then
    echo "FAIL_CLOSED: Candidate module failed kernel replay via leanchecker:" >&2
    cat "$TMP_DIR/leanchecker.log" >&2
    exit 1
fi

# Step D: Execute Host-side Semantic Verifier
VERIFY_LEAN="$TMP_DIR/VerifierLModule.lean"
{
    echo "import Lean"
    echo "import FrozenSpecModule"
    echo "import CandidateLModule"
    echo ""
    grep -vE '^\s*import\b' "$SCRIPT_DIR/VerifyLifted.lean"
    echo ""
    echo "#eval! VerifierTrustCore.runVerifyLifted \`CandidateLModule \`FrozenSpecModule \`frozen_target $PROHIBITED_LEAN_LIST"
} > "$VERIFY_LEAN"

OUTPUT="$TMP_DIR/verify_output.txt"
cd "$PROJECT_ROOT"

if ! lake env lean "$VERIFY_LEAN" > "$OUTPUT" 2>&1; then
    echo "VERIFY_LIFTED_FAILED: Type mismatch, circularity, non-standard axiom, or prohibited constants used:" >&2
    cat "$OUTPUT" >&2
    exit 1
fi

if ! grep -q "VERIFY_LIFTED_SENTINEL_OK" "$OUTPUT"; then
    echo "VERIFY_LIFTED_FAILED: Sentinel VERIFY_LIFTED_SENTINEL_OK missing from output:" >&2
    cat "$OUTPUT" >&2
    exit 1
fi

cat "$OUTPUT"
exit 0
