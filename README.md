# representation-lifting-s1

**Scientific Investigation Track:** Formal Representation Lifting & Structural Boundary Audit  
**Author / Principal Investigator:** Ivan Nestorov  
**Repository:** [https://github.com/VolMax-Studio/representation-lifting-s1](https://github.com/VolMax-Studio/representation-lifting-s1)  
**Toolchain Target:** Lean 4 (v4.34.0) / Mathlib v4.34.0 (commit `5ed2965256430c3649e86755f9576b54eca72435`)  
**Preregistration Specification:** [PREREGISTRATION_v0.6_CANDIDATE.md](file:///home/volmax-studio/volmax-projects/iot2/PORTFOLIO/representation-lifting-s1/PREREGISTRATION_v0.6_CANDIDATE.md)

---

## Overview

This repository hosts the formal preregistration, tooling, calibration fixtures, and evaluation harness for `representation-lifting-s1`.

### Claim-of-Record
> `representation-lifting-s1` is a preregistered case-study evaluation of whether a representation-first formalization strategy can:
> (a) discover a usable structure on externally sampled blind theorem statements, and
> (b) amortize its setup cost across preregistered theorem families.
> It does not test a universal claim that lifting produces shorter proofs.

---

## Setup & Mathlib Cache for Independent Verification

To set up and verify this project on a clean machine:

1. **Prerequisites:** Ensure `elan` and Lean 4 are installed.
2. **Fetch Pinned Dependencies:**
   ```bash
   lake update
   ```
3. **Download Precompiled Mathlib Oleans:**
   Because `lake-manifest.json` locks Mathlib to commit `5ed2965256430c3649e86755f9576b54eca72435`, run:
   ```bash
   lake exe cache get
   ```
   This automatically downloads and decompresses the precompiled `.olean` files directly from `https://cache.mathlib.org/mathlib4`, enabling instant elaboration without local compilation.

---

## Running Test Suites

All regression test suites run deterministically without external API dependencies:

```bash
python3 tests/test_check_bridge.py      # Verifies 12 bridge fixture branches and Identity Guard
python3 tests/test_verify_proof.py      # Verifies direct proof verification, binder matching, and Mathlib targets
python3 tests/test_verify_lifted.py     # Verifies structural lift, non-circularity, and dead bridge cheat rejection
python3 tests/test_executor_harness.py  # Verifies state machine loops, truncation handling, and H1 calibration
python3 tests/test_drand_schedule.py    # Verifies drand quicknet future-round invariants across 1000 grid points
```

---

## Architecture & Governance (v0.6)

1. **Method Mode Machine-Readable Deny-Lists (`admissibility/*.json`):**
   - Method Mode is the primary experimental regime. Models cannot query pre-packaged terminal lemmas (`Int.fib_succ_mul_fib_pred_sub_fib_sq`, `Nat.fib_gcd`, `Pell.Solution₁`, `IsPrimitiveRoot.geom_sum_eq_zero`).
   - The verifier (`checkDirectProhibited`) scans direct constant references in all newly authored candidate declarations (`NameSet`), without scanning transitively into Mathlib internals to prevent false rejections.
2. **Structural Lift Architecture:**
   - Role S defines representation types (`LiftDom`, `LiftCod`), representation map (`liftT`), closed proposition `LiftedClaim : Prop`, and specification `BridgeProp : Prop`.
   - Role L authors only `preservation_bridge : BridgeProp` and `lifted_theorem : LiftedClaim`.
   - Target theorem `executor_theorem` is mechanically synthesized by the trusted verifier:
     `fun xs => (preservation_bridge xs).mpr (lifted_theorem xs)`.
   - Non-circularity is strictly audited: `preservation_bridge ∉ Deps(lifted_theorem)`.
3. **Sequential Multi-Theorem Calibration State Machine (H1):**
   - `run_calibration_family` executes sequential $T_1 \to T_2$ runs in the same source context for both branches.
   - Evaluates the H1 marginal dividend test: $\Delta_L^{(2)} \le 0.50 \times \Delta_D^{(2)}$.
4. **Metric Definition Alignment:**
   - Direct: $W_D = W(\text{all newly authored candidate declarations required for proof})$.
   - Lifted: $W_L = W(\text{frozen representation prefix} + \text{proved bridge} + \text{lifted theorem})$.
5. **API Timeout & Truncation Normalization:**
   - Request timeout: 600s in `tools/executor_config.json` (eliminating length bias against Role L).
   - Responses cut off by token limit are normalized to `OUTPUT_TRUNCATED`.
