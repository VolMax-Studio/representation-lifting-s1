#!/usr/bin/env bash
# tools/verify_proof.sh
# Invokes Lean 4 meta-checker (tools/VerifyTarget.lean) to verify:
# 1. Exact definitional match between executor_theorem and frozen_target
# 2. Strict kernel axiom audit (A_observed ⊆ {propext, Classical.choice, Quot.sound})
# 3. Fail-closed scan (no sorry, admit, sorryAx)
# Part of representation-lifting-s1 experimental protocol.

set -euo pipefail

if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <frozen_target_file> <executor_lean_file> <executor_theorem_name>" >&2
    exit 2
fi

FROZEN_TARGET_FILE="$1"
EXECUTOR_LEAN_FILE="$2"
EXECUTOR_THEOREM="$3"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# 1. Fail-closed scan for unproved escape hatches in executor code
FORBIDDEN_PATTERN='(^|[^[:alnum:]_`])(sorry|admit)([^[:alnum:]_`]|$)|native_decide|^[[:space:]]*axiom([[:space:]]|$)'
if grep -En "$FORBIDDEN_PATTERN" "$EXECUTOR_LEAN_FILE" >/dev/null 2>&1; then
    echo "FAIL_CLOSED: Forbidden escape token detected in $EXECUTOR_LEAN_FILE" >&2
    exit 1
fi

# 2. Construct Lean verification harness combining frozen target, executor proof, and meta-checker
VERIFY_LEAN="$TMP_DIR/VerifyHarness.lean"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cat <<EOF > "$VERIFY_LEAN"
import Lean

-- Include core VerifyTarget definitions
$(cat "$SCRIPT_DIR/VerifyTarget.lean")

-- Include frozen target declaration
$(cat "$FROZEN_TARGET_FILE")

-- Include executor declarations
$(cat "$EXECUTOR_LEAN_FILE")

-- Execute meta-checker
#eval runVerifyTarget \`frozen_target \`$EXECUTOR_THEOREM
EOF

# 3. Execute Lean verification
OUTPUT="$TMP_DIR/verify_output.txt"
if ! lake env lean "$VERIFY_LEAN" > "$OUTPUT" 2>&1; then
    echo "VERIFICATION_FAILED: Proof does not elaborate, types mismatch, or non-standard axioms used:" >&2
    cat "$OUTPUT" >&2
    exit 1
fi

cat "$OUTPUT"
exit 0
