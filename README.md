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

The current preregistration is under **Text/Procedure Gate Review** (`PREREGISTRATION_v0.1_CANDIDATE.md`).
All gate blockers from initial candidate review have been resolved:
1. Exact literal target verification and kernel axiom audit ($A_{\text{observed}} \subseteq \{\texttt{propext}, \texttt{Classical.choice}, \texttt{Quot.sound}\}$).
2. Symmetric H1 amortization formula ($\Delta_L^{(2)}$ vs $\Delta_D^{(2)}$ executed sequentially in the same file).
3. Generic representation stub (`LiftDom`, `LiftCod`, `liftT`) with mechanical Identity Guard and target linkage verification.
4. Complete pre-frozen Negative Control outcome matrix and pre-frozen gnomon stub.
5. ProofNet-Verified mechanical filtering without subjective domain classification.
6. drand quicknet specification with BLS verification and rejection sampling.
7. Verified lexical tokenizer with 5 golden fixtures and whitespace invariance.
