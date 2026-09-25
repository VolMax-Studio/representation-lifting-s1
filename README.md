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

The current preregistration is under **Byte-Level Text/Procedure Gate Review** (`PREREGISTRATION_v0.4_CANDIDATE.md`).
All gate blockers have been resolved with pure Lean 4 kernel/MetaM checkers:
1. Pure Lean exact target match and fail-closed axiom audit (`tools/VerifyTarget.lean` + `tools/verify_proof.sh`).
2. Pure Lean representation stub and bridge linkage checker (`tools/CheckBridge.lean` + `tools/check_bridge.py`), verified on 11 frozen fixtures across all decision branches (AND Identity Guard, sequential dependent binder comparison, representation axiom whitelist).
3. Concrete execution harness state machine (`tools/executor_harness.py`) and discrete roles (S, D, L) with frozen budgets (3600s/15 turns for S, 10800s/30 turns for D and L).
4. Pinned model identities (`claude-sonnet-4-6` primary, `gpt-5.6-sol` replication) and live pre-freeze API smoke test (`tools/smoke_test_executor.py`).
5. Canonical ProofNet input bundle (header + helper + theorem) with automatic top-level import hoisting.
6. Symmetric H1 amortization formula ($\Delta_L^{(2)}$ vs $\Delta_D^{(2)}$ executed sequentially in the same file).
7. drand quicknet future-round formula ($r = \lfloor (u - 1692803367)/3 \rfloor + 2$ with $u = t_{\text{pub}} + 600$) with verified structural invariants.
8. Verified lexical tokenizer with 5 golden fixtures and whitespace invariance.
