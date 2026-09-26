#!/usr/bin/env bash
# tools/nontriviality_filter.sh
# Thin CLI wrapper for authoritative Gate 1 adjudicator (tools/nontriviality_filter.py).
# Tri-state fail-closed adjudicator contract:
#   0 = NONTRIVIAL (baseline elaborates with sorry; all 4 tactics fail to prove)
#   1 = TRIVIAL (proved by at least one basic tactic: rfl, decide, linarith, ring)
#   2 = INPUT_ERROR / BASELINE_INVALID (fails baseline elaboration with sorry, syntax error, unstripped sorry, etc.)
# Part of representation-lifting-s1 experimental protocol (v0.20).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/nontriviality_filter.py" "$@"
