#!/usr/bin/env bash
# tools/nontriviality_filter.sh
# Tests a theorem declaration snippet against 4 basic tactics under maxHeartbeats 200000.
# Tri-state fail-closed adjudicator contract:
#   0 = NONTRIVIAL (baseline elaborates with sorry; all 4 tactics fail to prove)
#   1 = TRIVIAL (proved by at least one basic tactic: rfl, decide, linarith, ring)
#   2 = INPUT_ERROR / BASELINE_INVALID (fails baseline elaboration with sorry, syntax error, unstripped sorry, etc.)
# Part of representation-lifting-s1 experimental protocol (v0.20).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <lean_file_or_declaration_snippet>" >&2
    exit 2
fi

TARGET_FILE="$1"
if [ ! -f "$TARGET_FILE" ]; then
    echo "INPUT_ERROR: Target file '$TARGET_FILE' does not exist." >&2
    exit 2
fi

# Fail-closed check 1: Target file must NOT contain unstripped 'sorry'
if grep -qw "sorry" "$TARGET_FILE"; then
    echo "INPUT_ERROR / BASELINE_INVALID: Target snippet contains unstripped 'sorry'." >&2
    exit 2
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# Extract and hoist any import statements from TARGET_FILE
IMPORTS=$(grep -E '^\s*import\b' "$TARGET_FILE" || true)
BODY=$(grep -v -E '^\s*import\b' "$TARGET_FILE" || true)

# Build header with clean import hoisting
build_lean_file() {
    local OUT_FILE="$1"
    local PROOF_BODY="$2"

    {
        echo "import Mathlib"
        if [ -n "$IMPORTS" ]; then
            echo "$IMPORTS" | grep -v 'import Mathlib' || true
        fi
        echo ""
        echo "set_option maxHeartbeats 200000"
        echo ""
        echo "$BODY := by"
        echo "  $PROOF_BODY"
    } > "$OUT_FILE"
}

# Step 1: Baseline elaboration check with sorry (Fail-Closed)
BASELINE_LEAN="$TMP_DIR/test_baseline.lean"
build_lean_file "$BASELINE_LEAN" "sorry"

if ! (cd "$PROJECT_ROOT" && lake env lean "$BASELINE_LEAN" >/dev/null 2>&1); then
    echo "INPUT_ERROR / BASELINE_INVALID: Statement failed baseline elaboration with sorry." >&2
    exit 2
fi

# Step 2: Probe the 4 basic tactics
TACTICS=("rfl" "decide" "linarith" "ring")

for TAC in "${TACTICS[@]}"; do
    CANDIDATE_LEAN="$TMP_DIR/test_${TAC}.lean"
    build_lean_file "$CANDIDATE_LEAN" "$TAC"

    if (cd "$PROJECT_ROOT" && lake env lean "$CANDIDATE_LEAN" >/dev/null 2>&1); then
        echo "TRIVIAL: Solved by tactic '$TAC'"
        exit 1
    fi
done

echo "NONTRIVIAL: Passed all 4 basic tactic tests."
exit 0
