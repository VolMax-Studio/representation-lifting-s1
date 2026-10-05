# EXECUTION_02 — Stable Provider-Availability Execution Instance

**Status:** CANDIDATE — requires one signed-tag ratification before execution

**Instance:** `s1-execution-02` (`A2`)

**Required tag:** `representation-lifting-s1-execution-02`

**Outcome visibility before the pre-outcome audit:** `NONE`

## Scope

This is a new execution instance, not a scientific amendment. It preserves the
ratified v0.21/A1 scientific design and all r8, r9, and `INFRA_RECOVERY_01`
records. It changes only the handling of objectively proven provider
unavailability before a model response is delivered.

The following remain unchanged: H0/H1/H2; pool and drand selection; targets;
`proofnet-108 -> proofnet-083 -> proofnet-267` order; control and calibration
families; prompts; scoring; admissibility; model identifier; Claude Code CLI
with Pro/OAuth; and the frozen executor harness/config. Direct Anthropic API
access and `/v1/messages` are prohibited for this instance.

## Bound prior state

- Ratified A1 r9 commit: `cf4d3a09e1a3bcc9c2496edd38d71b99f2f8a5b1`.
- Ratified `INFRA_RECOVERY_01` commit:
  `cbc3cdea97d50d7c8078308d1decd6589cbbdbe9`.
- The consumed recovery Gate 5 made three Claude Code CLI calls. Each returned
  `PRE_RESPONSE_TRANSPORT_FAILURE`, `rate_limit`, and
  `response_delivered=false`. The provider message stated that the weekly limit
  resets on 2026-10-07 at 04:00 Europe/Belgrade.
- The experimental block did not start. H0/H1/H2 remain unevaluated.

## Stable availability policy

The policy is frozen before execution and applies identically to Gate 5 and
every later protocol turn:

1. A delivered response is final and non-retryable, including an empty, wrong,
   refused, truncated, or model-mismatched response.
2. A retry is eligible only when the existing r9 transport classifier records
   `PRE_RESPONSE_TRANSPORT_FAILURE` and `response_delivered=false` from
   objective machine-readable evidence. Ambiguous delivery is non-retryable.
3. At most four availability attempts are permitted for one logical turn.
   Deterministic waits after eligible failures are 6 hours, 24 hours, and
   72 hours. Exhaustion is final `NOT_EVALUABLE_INFRA` for the instance; it does
   not authorize another recovery amendment.
4. Availability waits are transport queue time, recorded in provenance, and
   excluded from the already-frozen scientific role wallclock. CLI execution,
   model generation, verification, and all other work remain inside that
   wallclock.
5. Gate 5 attempt 1 is forbidden before
   `2026-10-07T04:05:00+02:00`, five minutes after the provider-stated reset.
   The Gate 5 start authorization expires at
   `2026-10-14T04:05:00+02:00`. No probe is sent merely to poll availability.

The fixed schedule is deliberately finite. It tolerates subscription-surface
unavailability without treating it as a model outcome, while preventing
retry-until-pass or outcome shopping.

## Execution and custody

`tools/execution_02.py` is the sole production entry point. Before creating any
new evidence namespace or invoking Claude it:

- verifies both prior signed tags and exact commits;
- verifies the preserved consumed-recovery evidence tree;
- verifies every manifest-bound frozen/runtime file;
- verifies the signed `EXECUTION_02` tag dereferences to current HEAD;
- compares critical worktree files byte-for-byte with the signed commit tree;
- refuses alternate production manifests and existing output namespaces.

Gate 5 uses no blind theorem content. Only a valid Gate 5 PASS may authorize the
complete block. The complete block order is fixed as: negative control;
`fibonacci`; `pell`; `roots_of_unity`; `proofnet-108`; `proofnet-083`;
`proofnet-267`. Outputs remain sealed and outcome visibility remains `NONE`
until a separate pre-outcome custody audit passes.

Ratification authorizes this one execution instance and its finite availability
policy. It does not authorize changing any scientific artifact or opening an
outcome early.
