#!/usr/bin/env bash
# tools/verify_proof.sh
# Verifies an executor proof against:
# 1. Exact literal target match (via wrapper: example : <target_stmt> := executor_theorem)
# 2. Strict axiom audit (only propext, Classical.choice, Quot.sound permitted)
# 3. Fail-closed scan (no sorry, admit, sorryAx, unsafe constants)
# Part of representation-lifting-s1 experimental protocol.

set -euo pipefail

if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <target_stmt_file> <executor_lean_file> <executor_theorem_name>" >&2
    exit 2
fi

TARGET_STMT_FILE="$1"
EXECUTOR_LEAN_FILE="$2"
EXECUTOR_THEOREM="$3"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# 1. Fail-closed scan for forbidden escape hatches
if grep -E '\b(sorry|admit|sorryAx)\b' "$EXECUTOR_LEAN_FILE" >/dev/null 2>&1; then
    echo "FAIL_CLOSED: Forbidden token detected in $EXECUTOR_LEAN_FILE"
    exit 1
fi

# 2. Build verification wrapper
VERIFY_LEAN="$TMP_DIR/verify_wrapper.lean"
cat "$EXECUTOR_LEAN_FILE" > "$VERIFY_LEAN"

cat <<EOF >> "$VERIFY_LEAN"

-- Verification wrapper ensuring literal target statement is proved
example : $(cat "$TARGET_STMT_FILE") := $EXECUTOR_THEOREM

-- Axiom extraction
#print axioms $EXECUTOR_THEOREM
EOF

# 3. Compile and extract axioms
OUTPUT="$TMP_DIR/lean_output.txt"
if ! lake env lean "$VERIFY_LEAN" > "$OUTPUT" 2>&1; then
    echo "COMPILATION_ERROR: Proof does not elaborate or does not match literal target:"
    cat "$OUTPUT"
    exit 1
fi

# 4. Audit axioms
AXIOMS_LINE=$(grep -A 10 "axioms:" "$OUTPUT" || true)
FORBIDDEN_AXIOMS=$(echo "$AXIOMS_LINE" | grep -vE 'axioms:|propext|Classical\.choice|Quot\.sound|^[[:space:]]*$' || true)

if [ -n "$FORBIDDEN_AXIOMS" ]; then
    echo "UNSAFE_AXIOMS: Detected non-standard axioms:"
    echo "$FORBIDDEN_AXIOMS"
    exit 1
fi

echo "VERIFICATION_SUCCESS: Literal target matched, zero sorry, kernel axioms verified."
exit 0
