# Independent Review — Amendment A1 Candidate r8

**Repository:** `VolMax-Studio/representation-lifting-s1`

**Reviewed exact candidate commit:**  
`9fbd8d067c728cf2a63348e60152bb2e84afa4f7`

**Reviewed tree:**  
`d3a487e2a3f7cc1147b42d74b7bd452c20c36a4d`

**Verdict:** **PASS — RATIFIABLE**

## Review Integrity

- Mathematical contents of `targets/*.lean`: **NOT INSPECTED**
- Sealed invalid pre-ratification run outputs: **NOT INSPECTED**
- Blind execution outcomes: **NONE INSPECTED**
- Review dependent on experimental outcome: **NO**

The review covered the complete r8 execution amendment and its remediation lineage, including:

- `AMENDMENT_A1_TRANSPORT.md`
- `evidence/amendment_a1/a1_transport_config.json`
- `tools/a1_surface_bridge.py`
- `tools/a1_activate.py`
- `tests/test_a1_surface_bridge.py`
- `tools/prepare_blind_targets.py`
- `tests/test_prepare_blind_targets.py`
- frozen `tools/executor_harness.py`
- frozen `tools/executor_config.json`
- pre-ratification deviation/remediation record

## Previous Findings

### F1 — A1.17 evidence preservation
**RESOLVED.**

Execution artifacts are partitioned by case and branch and sealed immediately on branch completion. Joint receipts bind the resulting sealed-transcript hashes.

### F2 — Gate 5 frozen-config verification
**RESOLVED.**

Gate 5 performs fail-closed preflight verification of the frozen executor configuration, frozen harness, A1 bridge, activation shim, tests, target preparer, amendment text, and pinned Claude Code executable before neutral inference.

### F3 — cross-case/cross-role overwrite risk
**RESOLVED.**

Blind, control and calibration executions use isolated case/branch artifact namespaces.

### F4 — ProofNet source identity
**RESOLVED.**

Target preparation fails closed unless the canonical ProofNet JSONL source SHA-256 matches the frozen source identity.

### F5 — control/calibration A1 custody
**RESOLVED.**

A1 evidence preservation now covers all experimental arms:

- Blind transfer: `D`, `S`, `L`
- Negative control: `D`, `L`
- Calibration families: `D1`, `D2`, `S1`, `L1`, `S2`, `L2`

Each branch receives an isolated artifact namespace and deterministic sealed transcript. Joint control and calibration receipts receive the same A1 custody bindings as the blind arm.

### F6 — observed provider model identity
**RESOLVED.**

Provider-emitted transport metadata is persisted as hash-addressed per-turn evidence and included in branch seals.

Receipt model-identity fields are derived from observed provider metadata rather than merely from the requested model identifier.

Provider model mismatch remains fail-closed.

### F7 — surface metadata / plan tier
**RESOLVED.**

The A1 configuration freezes surface plan-tier metadata and execution receipts preserve surface type, version and plan tier.

## Frozen-Core Integrity

The reviewed candidate preserves the frozen v0.21 execution core:

- `tools/executor_harness.py` remains byte-identical to the frozen SHA-256.
- `tools/executor_config.json` remains byte-identical to the frozen SHA-256.
- A1 operates through the separately reviewed activation/transport layer rather than modifying the frozen state machine.

The normative blind sequencing remains:

`D → S → L`

with branch isolation and no resampling.

## Gate 5

The default Gate 5 execution path performs preflight verification before sending the neutral inference probe.

The testing-only preflight bypass MUST NOT be used for the ratified Gate 5.

An admissible Gate 5 receipt MUST therefore show:

`preflight.preflight_pass = true`

before its inference result can be accepted.

This testing hook is **not considered a ratification blocker**, because it is not the default execution path and its use would be directly visible as a protocol violation.

## Independent Review Conclusion

No unresolved finding was identified that changes:

- scientific hypotheses;
- sampling;
- selected cases;
- state-machine semantics;
- scoring;
- control veto;
- branch isolation;
- model-identity enforcement;
- evidence custody; or
- Gate 5 fail-closed behavior.

Candidate:

`9fbd8d067c728cf2a63348e60152bb2e84afa4f7`

**SURVIVES INDEPENDENT REVIEW.**

**Final review verdict: PASS — RATIFIABLE.**

The next permitted sequence is:

1. archive and commit this independent review;
2. push the review record;
3. Ivan Nestorov creates a signed annotated tag pointing **exactly** to candidate commit `9fbd8d067c728cf2a63348e60152bb2e84afa4f7`;
4. push and verify the signed tag;
5. execute Gate 5 without the testing-only preflight bypass;
6. proceed to the ratified experimental execution only if Gate 5 passes.

Any modification to the candidate itself voids this review and requires review of the new exact commit.
