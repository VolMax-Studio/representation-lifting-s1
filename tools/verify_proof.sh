#!/usr/bin/env bash
# tools/verify_proof.sh
# Verification harness for Role D (Direct Proof Executor):
# 1. Enforces pinned Lake environment (lean-toolchain, lakefile.toml, lake-manifest.json).
# 2. Scans executor code for escape tokens (sorry, admit, native_decide, axiom).
# 3. Invokes Lean 4 meta-checker (tools/VerifyTarget.lean) to verify:
#    - Exact definitional match between executor_theorem and frozen_target
#    - Strict kernel axiom audit (A_observed ⊆ {propext, Classical.choice, Quot.sound})
#    - Machine-readable Method Mode Deny-List enforcement
# 4. Enforces exit code 0 and exact sentinel: VERIFICATION_SUCCESS.
# Part of representation-lifting-s1 experimental protocol (v0.6).

set -euo pipefail

if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <frozen_target_file> <executor_lean_file> <executor_theorem_name> [admissibility_json]" >&2
    exit 2
fi

FROZEN_TARGET_FILE="$1"
EXECUTOR_LEAN_FILE="$2"
EXECUTOR_THEOREM="$3"
ADMISSIBILITY_JSON="${4:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 1. Strict environment audit: Require pinned Lake project
if [ ! -f "$PROJECT_ROOT/lean-toolchain" ] || [ ! -f "$PROJECT_ROOT/lakefile.toml" ] || [ ! -f "$PROJECT_ROOT/lake-manifest.json" ]; then
    echo "ENVIRONMENT_INVALID: Pinned Lake project missing or incomplete in $PROJECT_ROOT." >&2
    exit 2
fi

# 2. Fail-closed scan for unproved escape hatches in executor code
FORBIDDEN_PATTERN='(^|[^[:alnum:]_`])(sorry|admit)([^[:alnum:]_`]|$)|native_decide|^[[:space:]]*axiom([[:space:]]|$)'
if grep -En "$FORBIDDEN_PATTERN" "$EXECUTOR_LEAN_FILE" >/dev/null 2>&1; then
    echo "FAIL_CLOSED: Forbidden escape token detected in $EXECUTOR_LEAN_FILE" >&2
    exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# 3. Extract and hoist imports to the absolute top
EXTRACT_SCRIPT='
import sys, re
imports = ["import Lean"]
for p in sys.argv[1:-1]:
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            if re.match(r"^\s*import\b", line):
                imp = line.strip()
                if imp not in imports:
                    imports.append(imp)
with open(sys.argv[-1], "w", encoding="utf-8") as out:
    for imp in imports:
        out.write(imp + "\n")
'

VERIFY_LEAN="$TMP_DIR/VerifyHarness.lean"

python3 -c "$EXTRACT_SCRIPT" "$FROZEN_TARGET_FILE" "$EXECUTOR_LEAN_FILE" "$SCRIPT_DIR/VerifyTarget.lean" "$TMP_DIR/imports.lean"

# Parse prohibited constants from admissibility JSON
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

# Extract all candidate-authored declaration names (theorems, lemmas, defs, abbrevs)
CANDIDATE_DECLS=$(python3 -c '
import sys, re
names = []
with open(sys.argv[1], "r", encoding="utf-8") as f:
    for line in f:
        m = re.match(r"^\s*(?:theorem|lemma|def|abbrev)\s+([a-zA-Z0-9_]+)", line)
        if m:
            names.append(f"`{m.group(1)}")
print("[" + ", ".join(names) + "]")
' "$EXECUTOR_LEAN_FILE")

cat "$TMP_DIR/imports.lean" > "$VERIFY_LEAN"
echo "" >> "$VERIFY_LEAN"
echo "-- Core VerifyTarget definitions" >> "$VERIFY_LEAN"
grep -vE '^\s*import\b' "$SCRIPT_DIR/VerifyTarget.lean" >> "$VERIFY_LEAN"
echo "" >> "$VERIFY_LEAN"
echo "-- Target statement" >> "$VERIFY_LEAN"
grep -vE '^\s*import\b' "$FROZEN_TARGET_FILE" >> "$VERIFY_LEAN"
echo "" >> "$VERIFY_LEAN"
echo "-- Executor declarations" >> "$VERIFY_LEAN"
grep -vE '^\s*import\b' "$EXECUTOR_LEAN_FILE" >> "$VERIFY_LEAN"
echo "" >> "$VERIFY_LEAN"
echo "#eval! runVerifyTarget \`frozen_target \`$EXECUTOR_THEOREM $CANDIDATE_DECLS $PROHIBITED_LEAN_LIST" >> "$VERIFY_LEAN"

# 4. Execute Lean verification strictly via pinned lake env lean
OUTPUT="$TMP_DIR/verify_output.txt"
cd "$PROJECT_ROOT"

if ! lake env lean "$VERIFY_LEAN" > "$OUTPUT" 2>&1; then
    echo "VERIFICATION_FAILED: Proof does not elaborate, types mismatch, or prohibited constants used:" >&2
    cat "$OUTPUT" >&2
    exit 1
fi

if ! grep -q "VERIFICATION_SUCCESS" "$OUTPUT"; then
    echo "VERIFICATION_FAILED: Sentinel VERIFICATION_SUCCESS missing from output:" >&2
    cat "$OUTPUT" >&2
    exit 1
fi

cat "$OUTPUT"
exit 0
