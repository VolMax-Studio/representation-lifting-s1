# Erratum to `PRE_RANDOMNESS_CUSTODY_BLOCKER_v0.20.md` (commit `64dd0c6`)

**Status:** append-only correction. The original file is not modified.
**Date:** 2026-09-29

## Corrections

1. **Retracted.** Section *Reproduction Policy* states: "Run2 produced byte-identical pool
   composition to run1's 359/367 completed cases (those not affected by INFRA_HANG)."
   This statement is false. Run1 aborted fail-closed and persisted only `INFRA_HANG.tsv`
   (see `evidence/pool-build-local-001/`). No classification of its remaining 359 cases was
   written anywhere. No run1/run2 comparison exists or can be made.

2. **Corrected.** Section *Required Next State*, "Observed", states "across two admissible
   full-corpus runs (run1: ABORTED/INFRA_HANG; run2: …)". Exactly **one** admissible
   full-corpus run exists: run2 (367/367, N_INFRA_HANG = 0). Run1 is an operational
   ABORTED/INFRA_HANG record, not an admissible run.

3. **Corrected scope of determinism evidence.** Cross-execution determinism evidence is
   limited to the eight cases of the isolated diagnostic (`infra8-isolated`), which received
   bucket assignments identical to run2 (8/8 POOL). The commit message of `64dd0c6`
   ("determinism confirmed across two executions") is to be read with that scope.

4. **Withdrawn.** Under "Not demonstrated", the item "The cause of the v0.21 amendment being
   required" is withdrawn as ill-formed. The v0.20 custody inconsistency is documented in the
   body of the blocker note. What remains not demonstrated is: the cause of run1's eight
   watchdog expirations; machine independence of the pool beyond one admissible full run
   plus eight isolated re-executions on the same host; any representation-lifting effect.

## Unaffected

The HALT decision, Check A (frozen code identity), Check B (8/8 identical classification),
the documented v0.20 prereg/analyzer inconsistency, and all hashes
(`pool_bundle_manifest.json` `aef332f69fb7bf70c0032dc05a383f8fea0085fecbd2ba22281c48ef4c36f7f6`,
`POOL.tsv` `398ddcb3d9e915edce681c0d59138950177d7eb096200795f927741fb9743212`) are unaffected.

No external anchor, drand round, or selection exists at the time of this erratum.
