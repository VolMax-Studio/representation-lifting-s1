# representation-lifting-s1

**Scientific Investigation Track:** Formal Representation Lifting & Structural Boundary Audit  
**Author / Principal Investigator:** Ivan Nestorov  
**Repository:** [https://github.com/VolMax-Studio/representation-lifting-s1](https://github.com/VolMax-Studio/representation-lifting-s1)  
**Toolchain Target:** Lean 4 (v4.34.0) / Mathlib v4.34.0  

---

## Overview

This repository hosts the formal preregistration, tooling, calibration fixtures, and evaluation harness for `representation-lifting-s1`.

### Claim-of-Record
> `representation-lifting-s1` is a preregistered case-study evaluation of whether a representation-first formalization strategy can:
> (a) discover a usable structure on externally sampled blind theorem statements, and
> (b) amortize its setup cost across preregistered theorem families.
> It does not test a universal claim that lifting produces shorter proofs.

---

## Directory Structure

```
.
├── PREREGISTRATION_v0.1_CANDIDATE.md  # Comprehensive preregistration specification
├── tools/
│   ├── count_lean_tokens.py          # Deterministic Lean 4 lexical token counter
│   ├── select_indices.py             # drand quicknet rejection-sampling script
│   ├── nontriviality_filter.sh       # 4-tactic mechanical nontriviality test
│   └── verify_proof.sh               # Fail-closed literal target & axiom verifier
├── fixtures/                         # Golden test fixtures for tokenizer verification
│   ├── nested_comments.lean
│   ├── quoted_identifiers.lean
│   ├── unicode_symbols.lean
│   ├── strings_with_comments.lean
│   └── escaped_strings.lean
└── calibration/                      # Pre-frozen calibration & control stubs
    └── ControlGnomonStub.lean        # Pre-frozen Negative Control gnomon stub
```

---

## Preregistration Status

The current preregistration is under **Byte-Level Text/Procedure Gate Review** (`PREREGISTRATION_v0.5_CANDIDATE.md`).
All gate blockers have been resolved with pure Lean 4 kernel/MetaM checkers:
1. Pure Lean exact target match and fail-closed axiom audit (`tools/VerifyTarget.lean` + `tools/verify_proof.sh`).
2. Pure Lean representation search verification (`tools/CheckBridge.lean` + `tools/check_bridge.py`), verifying proof-free `BridgeProp`, AND Identity Guard, sequential dependent binders, and representation axiom whitelist without `sorryAx`.
3. Proof-of-Method Provenance for Role L (`tools/VerifyLifted.lean` + `tools/verify_lifted.sh`): verifies exact target match, clean axioms, and kernel transitive dependency `preservation_bridge ∈ Deps*(executor_theorem)`. Rejects unlinked direct proofs with `LIFT_NOT_USED`.
4. Assembled Footprint Metric Binding: $W_L = W(\text{frozen representation prefix} + \text{proved bridge} + \text{L helpers} + \text{target proof})$.
5. Pinned Lake Project (`lean-toolchain`, `lakefile.toml`, `lake-manifest.json` pinned to Lean v4.34.0 and Mathlib `5ed29652…`). Tools enforce `lake env lean` and fail closed on `ENVIRONMENT_INVALID`.
6. Infrastructure Resilience & Classification (`tools/executor_config.json` + `tools/executor_harness.py`): up to 3 transport attempts with deterministic backoff (5s, 15s) for transient HTTP/network errors. Classified as `INFRA_FAILURE` / `NOT_EVALUABLE_INFRA`. Hard wall-clock timeout enforced across all turns.
7. Pinned model identities (`claude-sonnet-4-6` primary, `gpt-5.6-sol` replication) and live pre-freeze API smoke test (`tools/smoke_test_executor.py`) with strict model ID equality.
8. Symmetric H1 amortization formula ($\Delta_L^{(2)}$ vs $\Delta_D^{(2)}$ executed sequentially in the same file).
9. drand quicknet future-round formula ($r = \lfloor (u - 1692803367)/3 \rfloor + 2$ with $u = t_{\text{pub}} + 600$) with verified structural invariants.

