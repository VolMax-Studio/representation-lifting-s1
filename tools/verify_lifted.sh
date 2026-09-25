#!/usr/bin/env bash
# tools/verify_lifted.sh
# Verification harness for Role L (Lifted Proof Executor):
# 1. Enforces pinned Lake environment (lean-toolchain, lakefile.toml, lake-manifest.json).
# 2. Scans executor code for escape tokens (sorry, admit, native_decide, axiom).
# 3. Combines frozen representation prefix with executor proof.
# 4. Invokes tools/VerifyLifted.lean to verify:
#    - type(preservation_bridge) ≡ BridgeProp
#    - type(lifted_theorem) ≡ LiftedClaim
#    - Zero sorryAx and zero custom axioms in both proofs
#    - Non-circularity: preservation_bridge ∉ Deps(lifted_theorem)
#    - Method Mode deny-list enforcement
# 5. Enforces exit code 0 and exact sentinel: VERIFY_LIFTED_SENTINEL_OK.
# Part of representation-lifting-s1 experimental protocol (v0.6).

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

# 2. Fail-closed scan for unproved escape hatches in executor code
FORBIDDEN_PATTERN='(^|[^[:alnum:]_`])(sorry|admit)([^[:alnum:]_`]|$)|native_decide|^[[:space:]]*axiom([[:space:]]|$)'
if grep -En "$FORBIDDEN_PATTERN" "$EXECUTOR_LEAN_FILE" >/dev/null 2>&1; then
    echo "FAIL_CLOSED: Forbidden escape token detected in $EXECUTOR_LEAN_FILE" >&2
    exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# 3. Extract and hoist all imports to the absolute top
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

python3 -c "$EXTRACT_SCRIPT" "$FROZEN_TARGET_FILE" "$FROZEN_STUB_PREFIX" "$EXECUTOR_LEAN_FILE" "$SCRIPT_DIR/VerifyLifted.lean" "$TMP_DIR/imports.lean"

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

VERIFY_LEAN="$TMP_DIR/VerifyLiftedHarness.lean"

cat "$TMP_DIR/imports.lean" > "$VERIFY_LEAN"
echo "" >> "$VERIFY_LEAN"
echo "-- Core VerifyLifted definitions" >> "$VERIFY_LEAN"
grep -vE '^\s*import\b' "$SCRIPT_DIR/VerifyLifted.lean" >> "$VERIFY_LEAN"
echo "" >> "$VERIFY_LEAN"
echo "-- Target statement" >> "$VERIFY_LEAN"
grep -vE '^\s*import\b' "$FROZEN_TARGET_FILE" >> "$VERIFY_LEAN"
echo "" >> "$VERIFY_LEAN"
echo "-- Frozen Representation Prefix (from Role S)" >> "$VERIFY_LEAN"
grep -vE '^\s*import\b' "$FROZEN_STUB_PREFIX" >> "$VERIFY_LEAN"
echo "" >> "$VERIFY_LEAN"
# Extract candidate-authored declaration names (theorems, lemmas, defs, abbrevs)
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

echo "-- Executor Declarations (from Role L)" >> "$VERIFY_LEAN"
grep -vE '^\s*import\b' "$EXECUTOR_LEAN_FILE" >> "$VERIFY_LEAN"
echo "" >> "$VERIFY_LEAN"
echo "#eval! runVerifyLifted \`frozen_target \`BridgeProp \`LiftedClaim \`preservation_bridge \`lifted_theorem $CANDIDATE_DECLS $PROHIBITED_LEAN_LIST" >> "$VERIFY_LEAN"

# 4. Execute verification strictly via pinned lake env lean
OUTPUT="$TMP_DIR/verify_output.txt"
cd "$PROJECT_ROOT"

if ! lake env lean "$VERIFY_LEAN" > "$OUTPUT" 2>&1; then
    echo "VERIFICATION_FAILED: Proof does not elaborate, types mismatch, axioms non-standard, or circularity detected:" >&2
    cat "$OUTPUT" >&2
    exit 1
fi

if ! grep -q "VERIFY_LIFTED_SENTINEL_OK" "$OUTPUT"; then
    echo "VERIFICATION_FAILED: Sentinel VERIFY_LIFTED_SENTINEL_OK missing from output:" >&2
    cat "$OUTPUT" >&2
    exit 1
fi

cat "$OUTPUT"
exit 0
