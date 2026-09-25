#!/usr/bin/env bash
# tools/nontriviality_filter.sh
# Tests a theorem statement against 4 basic tactics under maxHeartbeats 200000.
# If any tactic succeeds, the problem is declared TRIVIAL (exit code 1).
# If all 4 tactics fail, the problem is declared NONTRIVIAL (exit code 0).
# Part of representation-lifting-s1 experimental protocol.

set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <lean_file_or_snippet>" >&2
    exit 2
fi

TARGET_FILE="$1"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

TACTICS=("rfl" "decide" "linarith" "ring")

for TAC in "${TACTICS[@]}"; do
    CANDIDATE_LEAN="$TMP_DIR/test_${TAC}.lean"
    cat <<EOF > "$CANDIDATE_LEAN"
import Mathlib

set_option maxHeartbeats 200000

-- Include target snippet
$(cat "$TARGET_FILE") := by
  $TAC
EOF

    # Attempt compilation with lean
    if lake env lean "$CANDIDATE_LEAN" >/dev/null 2>&1; then
        echo "TRIVIAL: Solved by tactic '$TAC'"
        exit 1
    fi
done

echo "NONTRIVIAL: Passed all 4 basic tactic tests."
exit 0
