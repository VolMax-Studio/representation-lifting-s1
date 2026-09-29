# Pre-Randomness Custody Blocker — Protocol v0.20

**Status:** BLOCKER  
**Discovery phase:** pre-anchor / pre-beacon / pre-selection  
**Frozen protocol commit:** `f3c8978b55985c0fc76a71ab3d57ba90917204e1`  
**Frozen protocol tag:** `representation-lifting-s1-freeze-v0.20`  
**Discovered by:** post-run2 pre-anchor review, 2026-09-29

---

## Context

The first admissible full-corpus pool construction completed successfully on run2:

| Field | Value |
|-------|-------|
| Total source entries | 367 |
| POOL | 362 |
| EXCLUDED_TRIVIAL | 1 |
| EXCLUDED_TOOLCHAIN_INCOMPATIBLE | 4 |
| INPUT_ERROR | 0 |
| INFRA_HANG | 0 |
| Partition invariant | satisfied |
| `pool_bundle_manifest.json` SHA-256 | `aef332f69fb7bf70c0032dc05a383f8fea0085fecbd2ba22281c48ef4c36f7f6` |
| `POOL.tsv` SHA-256 (from manifest) | `398ddcb3d9e915edce681c0d59138950177d7eb096200795f927741fb9743212` |

Additionally, two pre-anchor verification checks were performed and passed:

**Check A — Frozen code identity (run2):**  
All four frozen hashes recorded in run2's `pool_bundle_manifest.json` match the
values derivable from the frozen commit `f3c8978` exactly:

```
builder_sha256:     fccafe9e5a968098d99c7bd00015885c75be506c88854f220060862a8f7e3a65  ✓
filter_sha256:      de48d2c28a735d0128e49a3a714708bf8fe1cf60cff20a70cff251649d921fdf  ✓
source_commit:      160414332dc196583f6c37c310b420d2a3b07c58                         ✓
source_jsonl_sha256: 381f4a06548a4ff6d9b923633c94a97b9c70f41033e13023aae31e1161b7f142  ✓
```

**Check B — Evaluator determinism (8/8 INFRA_HANG cases re-evaluated):**  
The eight cases previously associated with run1 INFRA_HANG were independently
re-executed (sleep-inhibited) and then compared against run2 classification:

```
proofnet-062 | iso=POOL | run2=POOL | ✓ MATCH
proofnet-117 | iso=POOL | run2=POOL | ✓ MATCH
proofnet-118 | iso=POOL | run2=POOL | ✓ MATCH
proofnet-119 | iso=POOL | run2=POOL | ✓ MATCH
proofnet-158 | iso=POOL | run2=POOL | ✓ MATCH
proofnet-159 | iso=POOL | run2=POOL | ✓ MATCH
proofnet-160 | iso=POOL | run2=POOL | ✓ MATCH
proofnet-162 | iso=POOL | run2=POOL | ✓ MATCH
```

**No external pool timestamp anchor has been issued.**  
**No drand round has been scheduled or retrieved.**  
**No blind selection has been performed.**

---

## Discovered v0.20 Custody Inconsistency

The frozen preregistration (`PREREGISTRATION_v0.20_CANDIDATE.md`) and the frozen
analyzer (`tools/analyze.py`) impose different, mutually incompatible requirements
on the pool anchor receipt.

### Preregistration requirement (line 259)

> **Validation Rule:** Must bind both `pool_sha256` and `commitment_sha256`,
> must have `verification_status: "ANCHOR_VERIFIED"`, and must verify
> `verified_timestamp_unix <= published_at_unix`.

The preregistration further states (line 105):

> The external public timestamp anchor … must anchor the SHA-256 digest of the
> **entire `pool_bundle_manifest.json` file**.

### Frozen `tools/analyze.py::validate_selection` (lines ~290–297)

The frozen analyzer:

1. Checks `verification_status == "ANCHOR_VERIFIED"` ✓ (matches)
2. Checks `pool_sha256` equality ✓ (matches)
3. **Requires strict equality:** `int(anchor_ts) != pub_time_int` → raises error

   This is stronger than `<=` and is operationally incompatible: a truthful
   external timestamp for a commitment file cannot in general be known before
   `published_at_unix` is written into that same file.

4. **Does not validate `commitment_sha256`** ✗ (preregistration requires it)
5. **Does not validate the SHA-256 of `pool_bundle_manifest.json`** ✗
   (preregistration requires it)

### Frozen test suite

The frozen test suite encodes the strict equality behaviour (`anchor_ts != pub_time`
must fail) but does not adversarially test that `commitment_sha256` is verified.
No frozen test covers the whole-manifest hash requirement.

### No generator for `pool_commitment.json`

No frozen tool generates `pool_commitment.json`. It must be constructed manually,
which means `published_at_unix` is chosen at authoring time — making the strict
equality condition `anchor_ts == published_at_unix` operationally impossible to
satisfy with a truthful, externally-issued timestamp.

---

## Consequence

Proceeding by manually constructing receipts that merely satisfy the frozen
analyzer would not satisfy the full frozen v0.20 preregistration text. An
audit or independent replication would find the contradiction between the
two normative sources without any indication of which governs.

The failure mode is not detectable post-hoc from the pool state alone; it would
only surface during analysis phase validation or independent audit, at which
point the pre-randomness window would have closed.

---

## Decision

**No pool anchor SHALL be issued under the unresolved v0.20 custody contract.**

A pre-randomness custody amendment SHALL be frozen and human-ratified before
any external timestamp anchor, drand round retrieval, or blind selection is
performed.

The amendment is restricted strictly to custody/timestamp semantics and the
`pool_anchor_receipt` validation logic. It **MUST NOT** alter:

- the ProofNet source corpus or its pinned commit/SHA-256;
- Gate 1 or Gate 2 filtering semantics;
- the frozen pool-builder logic (`tools/build_pool.py`);
- the observed 362-case candidate pool (`aef332…` manifest);
- the representation-lifting hypotheses H1 and H2;
- the experimental scoring rules or verdict semantics.

---

## Proposed Amendment Scope (v0.21)

The minimal amendment to resolve this blocker without altering experimental
parameters:

1. **Authoritative timestamp definition:** The external timestamp T₁ is the
   `verified_timestamp_unix` from the Rekor/RFC 3161/OTS receipt for the entire
   `pool_bundle_manifest.json`. This is the single authoritative pool publication
   time.

2. **`pool_commitment.json` generation:** A frozen tool (or explicit procedure)
   derives `published_at_unix = T₁` deterministically after anchor issuance.
   `pool_commitment.json` is a derived custody record, not a pre-authored file.

3. **`pool_anchor_receipt.json` (v2 schema):** Explicitly records:
   - `manifest_sha256`: whole-manifest SHA-256 (`aef332…`)
   - `pool_sha256`: POOL.tsv SHA-256 (from manifest `bundle_files`)
   - `commitment_sha256`: SHA-256 of the derived `pool_commitment.json`
   - `verified_timestamp_unix`: T₁
   - `verification_status: "ANCHOR_VERIFIED"`

4. **`analyze.py` updated validation:** Verifies all five fields above;
   replaces `==` with `<=` for timestamp comparison (or enforces `==` only
   after `published_at_unix` is known to equal T₁ by construction).

5. **Adversarial tests:** Test suite must cover `commitment_sha256` mismatch
   and whole-manifest hash mismatch as explicit fail-closed cases.

The observed 362-case pool composition and `aef332…` manifest hash are
**unaffected** by this amendment.

---

## Reproduction Policy

A second full pool build is not required by frozen v0.20.

Run2 produced byte-identical pool composition to run1's 359/367 completed cases
(those not affected by INFRA_HANG). The 8-case isolated diagnostic confirmed all
8 previously hung cases are POOL-classified under unchanged evaluation, with
elapsed times 279–417 s (well within 600 s watchdog).

If any additional full reproduction is performed before anchoring, it is
corroborative only and governed by this precommitted rule:

- Byte-identical deterministic output → corroborative reproduction PASS
- Any deterministic-output mismatch → HALT and investigate
- No run may be selected or discarded because its pool composition is
  scientifically preferable

No external pool anchor shall be issued while any such mismatch remains unresolved.

---

## Pre-Randomness Exposure

The eight cases previously associated with INFRA_HANG were independently
re-executed before anchoring. All eight were classified as POOL under the
unchanged v0.20 evaluator (isolated diagnostic, sleep-inhibited).

This constitutes pre-randomness **diagnostic information exposure** (pool
composition is now known before blind selection), but **not experimental S/D/L
outcome exposure** (no theorems have been evaluated for representation-lifting
effect; no selection has been performed).

The pool composition and future blind selection rule **MUST NOT** be modified
in response to this information.

---

## Required Next State

```
HALT at pool-anchor boundary.
Pending: ratified custody amendment (v0.21).
No anchor. No drand. No selection.
```

**Observed:**  
The frozen v0.20 pool builder completed the live corpus evaluation across two
admissible full-corpus runs (run1: ABORTED/INFRA_HANG; run2: 367/367, N_INFRA_HANG=0)
and produced a consistent 362-case candidate pool. The fail-closed mechanism
operated correctly in both runs. A pre-anchor review then identified a normative
contradiction between the frozen preregistration and the frozen analyzer regarding
the anchor receipt validation contract.

**Not demonstrated:**  
The cause of the v0.21 amendment being required, machine-independent pool
composition beyond two runs on the same host, or any representation-lifting
effect. H1, H2, selection, and scoring remain untouched.
