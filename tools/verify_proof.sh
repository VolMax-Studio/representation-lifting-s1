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

# 2. Extract imports from target and executor files to place them at the absolute top
EXTRACT_SCRIPT='
import sys, re
imports = ["import Lean"]
body = []
for p in sys.argv[1:-1]:
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            if re.match(r"^\s*import\b", line):
                imp = line.strip()
                if imp not in imports:
                    imports.append(imp)
            else:
                body.append(line)
with open(sys.argv[-1], "w", encoding="utf-8") as out:
    for imp in imports:
        out.write(imp + "\n")
'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERIFY_LEAN="$TMP_DIR/VerifyHarness.lean"

# Combine imports at top, followed by VerifyTarget meta-checker, target, executor, and eval
python3 -c "$EXTRACT_SCRIPT" "$FROZEN_TARGET_FILE" "$EXECUTOR_LEAN_FILE" "$SCRIPT_DIR/VerifyTarget.lean" "$TMP_DIR/imports.lean"

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
echo "#eval runVerifyTarget \`frozen_target \`$EXECUTOR_THEOREM" >> "$VERIFY_LEAN"

# 3. Execute Lean verification
OUTPUT="$TMP_DIR/verify_output.txt"
CMD=(lean "$VERIFY_LEAN")
if command -v lake >/dev/null 2>&1 && [ -f "lakefile.toml" ]; then
    CMD=(lake env lean "$VERIFY_LEAN")
fi

if ! "${CMD[@]}" > "$OUTPUT" 2>&1; then
    echo "VERIFICATION_FAILED: Proof does not elaborate, types mismatch, or non-standard axioms used:" >&2
    cat "$OUTPUT" >&2
    exit 1
fi

cat "$OUTPUT"
exit 0
