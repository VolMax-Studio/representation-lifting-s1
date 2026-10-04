# INFRA_RECOVERY_01 — Append-Only Gate 5 Infrastructure Recovery Amendment

**Status:** CANDIDATE — AWAITING INDEPENDENT REVIEW AND HUMAN RATIFICATION

**Scope:** custody and implementation conformance only

**Scientific protocol version:** unchanged

**Maximum authorized recovery executions:** one

## 1. Bound prior state

The exact ratified A1 r9 candidate is commit
`cf4d3a09e1a3bcc9c2496edd38d71b99f2f8a5b1`, ratified by signed annotated tag
`representation-lifting-s1-amendment-a1-r9`.

Its fresh Gate 5 attempt produced append-only evidence under
`evidence/amendment_a1/r9_execution/gate5/`. That attempt is permanently:

`FAILED — PRE_RESPONSE INFRA / rate_limit`

The preserved transport metadata records CLI return code `1`, classification
`PRE_RESPONSE_TRANSPORT_FAILURE`, `response_delivered=false`, attempts `1/1`, and
provider-reported model `claude-sonnet-4-6`. No `gate5_receipt.json` exists. The
experimental block did not start and outcome visibility remained `NONE`.

This evidence is admissible custody evidence of the infrastructure failure. It
is not a Gate 5 PASS, scientific result, model outcome, or evidence for H0/H1/H2.
It MUST NOT be deleted, rewritten, moved, normalized, replaced, or retroactively
relabeled. Its complete file set and SHA-256 bindings are frozen in
`evidence/amendment_a1/INFRA_RECOVERY_01_CONFIG.json`.

No provider root cause beyond the observed `rate_limit` signal is claimed.

## 2. Custody precedent and limitation

The earlier `infra8-isolated` episode supplies only a custody pattern: preserve
the failed infrastructure run, do not retroactively validate it, and give any
authorized recovery a separate identity and provenance. That episode occurred
before anchor, randomness, and selection. The present event occurred at a
ratified Gate 5. Therefore `infra8-isolated` does not itself authorize a rerun;
this independently reviewed and human-ratified amendment is required.

## 3. Implementation-conformance defect

The ratified Gate 5 wrapper called `run_gate5_probe()` without the frozen executor
configuration. Its default `{}` caused `a1_call_surface()` to resolve an implicit
one-attempt budget. The already-frozen `tools/executor_config.json` instead binds
the transport policy to three attempts, retryable codes `[408,429,500,502,503,504]`,
backoffs `5s` then `15s`, and request timeout `600s`.

This amendment does not invent retries after observing a rate limit. It restores
implementation conformance by loading the already-frozen executor config,
verifying its frozen SHA-256, and passing that config unchanged to the Gate 5 call
path. `tools/executor_config.json` and `tools/executor_harness.py` remain unchanged.

## 4. Single authorized recovery Gate 5

After independent review and a human-signed annotated tag named
`representation-lifting-s1-infra-recovery-01`, exactly one recovery execution is
authorized through `tools/a1_infra_recovery_01.py --execute-recovery-gate5`.

The recovery:

- writes only to `evidence/amendment_a1/infra_recovery_01/gate5/`;
- refuses to start if that namespace already exists;
- writes an exclusive `RECOVERY_STARTED.json` before inference, so interruption
  or failure consumes the sole recovery execution;
- verifies the preserved failed-r9 evidence file set and hashes;
- verifies the signed recovery tag points to the current candidate commit;
- verifies all bound frozen files before inference;
- uses the same `claude-sonnet-4-6`, neutral system/user probe, exact-match rule,
  model identity checks, tool/MCP checks, and preflight bindings as r9 Gate 5;
- permits at most the frozen three attempts with frozen `5s/15s` backoff.

Retry is permitted only after proven pre-response transport/provider/client
failure. There is no retry after any genuine response (including empty), wrong
exact-match content, model mismatch, tool/MCP exposure, unproven synthetic event,
or delivered-response protocol failure. There is no outcome shopping and no
retry-until-pass behavior.

If all three frozen attempts fail before response, or if the single recovery
execution otherwise fails, the state is `HALT`. This amendment does not authorize
a second recovery amendment or another Gate 5 execution.

## 5. Scientific invariants and downstream gate

This amendment changes none of H0/H1/H2, selected ProofNet cases or order,
negative control, calibration families, prompts, model assignment, targets,
budgets, scoring, admissibility, `tools/analyze.py`, executor harness/config,
drand, randomness, selection, or prior evidence.

Until recovery Gate 5 PASS, all experimental execution remains blocked. Only a
valid PASS authorizes the complete block, from the negative control through
`fibonacci`, `pell`, `roots_of_unity`, `proofnet-108`, `proofnet-083`, and
`proofnet-267`, followed by the pre-outcome protocol audit. Outcome opening remains
separately gated on that audit PASS.

Current state: experimental block `NOT STARTED`; H0/H1/H2 `NOT EVALUATED`;
`OUTCOME VISIBILITY: NONE`.
