# representation-lifting-s1: PREREGISTRATION v0.9 CANDIDATE
**Status:** SUPERSEDED BY v0.10 CANDIDATE (Claude Gate BLOCKED on command elaborator hijack; resolved by compiled adjudicator executable in v0.10)  
**Author / Principal Investigator:** Ivan Nestorov  
**Target Toolchain:** Lean 4 (v4.34.0) / Mathlib v4.34.0 (commit `5ed2965256430c3649e86755f9576b54eca72435`)  
**Repository Location:** `PORTFOLIO/representation-lifting-s1/`  
**GitHub Tracking Repo:** `https://github.com/VolMax-Studio/representation-lifting-s1`  
**Date:** 2026-09-25  

---

## 1. Claim-of-Record

> **Claim-of-Record:**  
> `representation-lifting-s1` is a preregistered case-study evaluation of whether a representation-first formalization strategy can:  
> (a) discover a usable structure on externally sampled blind theorem statements, and  
> (b) amortize its setup cost across preregistered theorem families.  
> It does not test a universal claim that lifting produces shorter proofs.

### Scope and Boundary Declarations
- **Non-Conflation of Dimensions:** Mathematical correctness (L0) is distinct from formalization footprint, execution time, and algorithmic performance (L3).
- **Motivation Boundary:** The Gaussian-integer composition theorem for primitive Pythagorean triples (`primitive-composition-square-content-s1`) serves strictly as historical motivation; it is **excluded** from the evaluation dataset.
- **P10 Decoupling:** This preregistration does not evaluate P10 underdetermination, observational equivalence, or world invariants ($W_E \to T(W_E)$). The failure or success of `representation-lifting-s1` has zero evidential bearing on P10 claims.

---

## 2. Experimental Arms & Architecture

The study consists of three strictly separated arms:

```
                               ┌──────────────────────────────────────────────────────────┐
                               │                 representation-lifting-s1                │
                               └────────────────────────────┬─────────────────────────────┘
                                                            │
         ┌──────────────────────────────────────────────────┼──────────────────────────────────────────────────┐
         │                                                  │                                                  │
         ▼                                                  ▼                                                  ▼
┌─────────────────────────────────┐        ┌─────────────────────────────────┐        ┌─────────────────────────────────┐
│     Calibration-Family Arm      │        │        Blind Transfer Arm       │        │      Negative Control Arm       │
├─────────────────────────────────┤        ├─────────────────────────────────┤        ├─────────────────────────────────┤
│ • Fibonacci (Cassini + Additive)│        │ • ProofNet-Verified (367 base)  │        │ • Sum of odd numbers = n²       │
│ • Pell (Fund. unit + Product)   │        │ • Mechanical nontriviality      │        │ • Frozen Gnomon BridgeProp      │
│ • Roots of Unity (Geom sum + Re)│        │ • Verbatim compile on 4.34      │        │ • Symmetric outcome matrix      │
│ Evaluates: Symmetric marginal   │        │ • drand quicknet (N=3 cases)    │        │ • Falsifies metric bias         │
│            amortization (T1, T2)│        │ Evaluates: Discovery & Step 1   │        │ Evaluates: Scoring integrity    │
└─────────────────────────────────┘        └─────────────────────────────────┘        └─────────────────────────────────┘
```

### 2.1 Calibration-Family Arm (Symmetric Amortization & Marginal Cost)
Evaluates whether establishing an explicit representation layer ($T: \text{LiftDom} \to \text{LiftCod}$) and preservation bridge incurs an initial setup footprint penalty on theorem $T_1$, but yields a significant marginal footprint reduction on a subsequent related theorem $T_2$ from the same family.

**Real Cumulative Multi-Theorem Execution Rule:**  
Both branches ($L$ and $D$) execute $T_2$ as a **real cumulative compilation artifact**:
1. **Direct Branch:** $D_1$ declarations are compiled as an immutable frozen module prefix prior to $D_2$ elaboration. $W_D(T_1 + T_2) = \text{tokens}(D_1 + D_2)$. Marginal cost $\Delta_D^{(2)} = W_D(T_1 + T_2) - W_D(T_1)$.
2. **Lifted Branch:** $T_2$ reuses the representation core ($\text{LiftDom}, \text{LiftCod}, \text{liftT}, \text{invariant}$) and proved representation lemmas from $T_1$, but receives a fresh, independently verified specification ($\text{LiftedClaim}_{T2}, \text{BridgeProp}_{T2}$) linked to $T_2$'s frozen target. Cumulative artifact is $S_1 + L_1 + S_2 + L_2$. Marginal cost $\Delta_L^{(2)} = W_L(T_1 + T_2) - W_L(T_1)$.

**Frozen Lean Calibration Statements (`calibration/`):**

1. **Fibonacci Family (`calibration/fibonacci_t1.lean`, `calibration/fibonacci_t2.lean`):**
   - $T_1$ (Cassini identity, mathematically well-posed for $1 \le n$):
     ```lean
     import Mathlib.Data.Int.Fib.Lemmas
     theorem frozen_target (n : ℕ) (hn : 1 ≤ n) :
         (Nat.fib (n + 1) : ℤ) * (Nat.fib (n - 1) : ℤ) - (Nat.fib n : ℤ)^2 = (-1)^n
     ```
   - $T_2$ (Additive formula):
     ```lean
     import Mathlib.Data.Nat.Fib.Basic
     theorem frozen_target (m n : ℕ) :
         Nat.fib (m + n + 1) = Nat.fib m * Nat.fib n + Nat.fib (m + 1) * Nat.fib (n + 1)
     ```
   - *Lifted Representation:* Matrix ring $M_2(\mathbb{Z})$ with generator $Q = \begin{pmatrix} 1 & 1 \\ 1 & 0 \end{pmatrix}$. $T_1$ maps to determinant multiplicativity; $T_2$ maps to matrix power addition.

2. **Pell Family (`calibration/pell_t1.lean`, `calibration/pell_t2.lean`):**
   - $T_1$ (Solution composition):
     ```lean
     import Mathlib
     theorem frozen_target (x₁ y₁ x₂ y₂ : ℤ)
         (h₁ : x₁^2 - 2 * y₁^2 = 1) (h₂ : x₂^2 - 2 * y₂^2 = 1) :
         (x₁ * x₂ + 2 * y₁ * y₂)^2 - 2 * (x₁ * y₂ + x₂ * y₁)^2 = 1
     ```
   - $T_2$ (Square / double solution):
     ```lean
     import Mathlib
     theorem frozen_target (x y : ℤ) (h : x^2 - 2 * y^2 = 1) :
         (x^2 + 2 * y^2)^2 - 2 * (2 * x * y)^2 = 1
     ```
   - *Lifted Representation:* Ring of integers $\mathbb{Z}[\sqrt{2}]$ with norm map $N(a + b\sqrt{2}) = a^2 - 2b^2 = 1$.

3. **Roots of Unity Family (`calibration/roots_of_unity_t1.lean`, `calibration/roots_of_unity_t2.lean`):**
   - $T_1$ (Trigonometric cosine vanishing sum):
     ```lean
     import Mathlib
     theorem frozen_target (n : ℕ) (hn : 2 ≤ n) :
         ∑ k ∈ Finset.range n, Real.cos (2 * Real.pi * k / n) = 0
     ```
   - $T_2$ (Trigonometric sine vanishing sum):
     ```lean
     import Mathlib
     theorem frozen_target (n : ℕ) (hn : 2 ≤ n) :
         ∑ k ∈ Finset.range n, Real.sin (2 * Real.pi * k / n) = 0
     ```
   - *Lifted Representation:* Complex roots of unity $\zeta_n^k = e^{2\pi i k / n}$, reducing both sums to the geometric series $\sum_{k=0}^{n-1} \zeta_n^k = 0$.

### 2.2 Blind Transfer Arm (Discovery Feasibility)
Evaluates whether a representation-first search can discover a valid representation and preservation bridge on externally sourced problems without hindsight, and records the resulting completion outcomes.
- Under the 60-minute representation search ceiling, `LIFT-NOT-FOUND` is an expected, legitimate descriptive finding of H2 (quantifying the empirical boundary of automatic representation discovery), rather than an experimental failure.
- Does **not** assert claims regarding $T_2$ amortization (as external benchmark items do not come paired with predetermined structural sibling theorems).

### 2.3 Negative Control Arm (Scoring Integrity Check)
- **Target Statement:**
  ```lean
  theorem sum_odd_sq (n : ℕ) :
      ∑ k ∈ Finset.range n, (2 * k + 1) = n^2
  ```
- **Direct Path:** Direct induction or basic arithmetic summation over `Finset.range`.
- **Lifted Path:** Pre-frozen gnomon decomposition stub (`calibration/ControlGnomonStub.lean` committed before execution), providing `BridgeProp` and `LiftedClaim`.
- **Pre-frozen Control Outcome Matrix:**
  | Observed Outcome | Formalization Footprint | Verdict | Operational Action |
  |---|---|---|---|
  | `D-ONLY` | N/A | **`CONTROL_PASS`** | Integrity confirmed; direct wins on flat problem. |
  | `BOTH` | $W_D < W_L$ | **`CONTROL_PASS`** | Integrity confirmed; metric correctly penalizes unnecessary lift. |
  | `L-ONLY` | N/A | **`COMPROMISED`** | Protocol failure; direct branch starved or broken. |
  | `BOTH` | $W_L \le W_D$ | **`COMPROMISED`** | Protocol failure; metric possesses structural bias toward lifting. |
  | `NEITHER` | N/A | **`CONTROL_INCONCLUSIVE`**| Both failed; raw data preserved, no method-level conclusion. |

---

## 3. Trusted Verification Architecture (v0.9)

### 3.1 Modular Separation & Three-Tier Trust Boundary
In v0.9, candidate execution is decoupled entirely from the host semantic checker environment. The system establishes three strict execution tiers:

```
TrustedTargetModule.lean / FrozenSpecModule.lean
  │
  ▼
CandidateModule.lean (Authored in Isolated Subprocess Sandbox)
  │
  │ lake env lean -o CandidateModule.olean CandidateModule.lean
  ▼
CandidateModule.olean
  │
  │ lake env leanchecker CandidateModule (Lean 4 Kernel Replay)
  ▼
kernel-replayed CandidateModule.olean
  │
  ▼
VerifierModule.lean (Host-side Semantic Adjudicator)
```

1. **Tier 1: Candidate Module Isolation & Provenance:**
   Candidate declarations are defined exclusively and strictly by their compilation module:
   $$\boxed{ \text{CandidateDecl}(c) \iff \text{module}(c) = \text{CandidateModule} }$$
   - Eliminates all naming heuristics, namespace matching (`CandidateExecutor`), and trust exceptions (`isTrusted`, `_aux`, `_eval`, `_root_`, `private`).
   - Every declaration authored in `CandidateModule` (regardless of identifiers or namespaces) is tracked with index `idx(CandidateModule)`.

2. **Tier 2: Mandatory Kernel Replay (`leanchecker`):**
   Before the host semantic checker executes, the candidate `.olean` is independently checked by `lake env leanchecker CandidateModule`.
   - `leanchecker` replays every declaration in the `.olean` through the Lean 4 kernel with full type checking.
   - Any attempt to bypass typing via `set_option debug.skipKernelTC true` or untyped meta-modifications fails closed during kernel replay.

3. **Tier 3: OS / Process Sandbox & Defense-in-Depth Static Scanning:**
   - **Environment Sanitization:** API secrets, tokens, and credentials (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GITHUB_TOKEN`, `SSH_AUTH_SOCK`) are scrubbed from candidate subprocesses.
   - **Filesystem Mutation Guard:** A cryptographic SHA-256 snapshot of trusted repository files (`tools/`, `fixtures/`, `calibration/`, `admissibility/`) is verified before and after candidate compilation. Any unauthorized creation, modification, or deletion outside the temporary candidate build directory immediately terminates with `FAIL_CLOSED`.
   - **Static Defense-in-Depth:** Fails closed prior to elaboration if candidate code references:
     - Escape tokens: `sorry`, `admit`, `native_decide`, `axiom`
     - Command-level meta-programming: `run_cmd`, `#eval`, `initialize`, `unsafe`, `elab`, `macro`, `syntax`
     - Dangerous options: `set_option debug.*`
     - Compiler escape hatches: `@[implemented_by]`
     - IO manipulations: `IO.FS`, `IO.Process`
     - Trust core spoofing: `\bVerifierTrustCore\b`

### 3.2 Evaluation Regimes: Method Mode vs. Ecosystem Mode
1. **Method Mode (Primary Regime):**
   - Evaluates discovery from first principles against machine-readable deny-lists (`admissibility/<case>.json`).
   - All declarations in `CandidateModule` are audited for prohibited constants (exact and prefix match).
   - `Nat.fib_add_two` is recognized as the foundational recurrence of `Nat.fib` (marked `@[simp]`) and permitted. Terminal shortcuts (`Int.fib_succ_mul_fib_pred_sub_fib_sq`, `Nat.fib_add`, `Nat.fib_gcd`) are strictly forbidden.
2. **Ecosystem Mode (Secondary Baseline):**
   - Unconstrained Mathlib baseline for sensitivity evaluation.

---

## 4. Operational Protocols: Search, Gate, & Structural Lift

### 4.1 Mechanical Representation-Search Protocol (Role S)
- Produces specification stub: `LiftDom`, `LiftCod`, `liftT`, `LiftedClaim`, `BridgeProp`.
- Compiled as `CandidateSModule.lean`, replayed via `leanchecker`, and verified by `tools/CheckBridge.lean`.
- Identity Guard: $\text{isDefEq}(\text{LiftDom}, \text{LiftCod}) \land \text{isDefEq}(\text{liftT}, @\text{id LiftDom}) \implies \textbf{LIFT-NOT-FOUND}$.
- Axiom Audit: Zero `sorryAx` anywhere in specification.
- Linkage: Non-tautological equivalence connecting target to `LiftedClaim` and containing `liftT`.
- Sentinel: `CHECK_BRIDGE_SENTINEL_OK`.

### 4.2 Structural Lift Architecture & Target Synthesis (Role L)
- Authors strictly `preservation_bridge : BridgeProp` and `lifted_theorem : LiftedClaim`.
- Compiled as `CandidateLModule.lean` (importing `FrozenSpecModule`), replayed via `leanchecker`.
- Host-side verifier (`tools/VerifyLifted.lean`):
  - Audits kernel axioms of both candidate theorems.
  - Verifies transitive non-circularity strictly across declarations in `CandidateLModule`:
    $$\texttt{preservation\_bridge} \notin \text{Deps}^*(\texttt{lifted\_theorem})$$
  - Mechanically synthesizes `synthesized_target := fun xs => (preservation_bridge xs).mpr/.mp (lifted_theorem xs)`.
  - Asserts $\text{type}(\texttt{synthesized\_target}) \equiv_{\text{def}} \text{type}(\texttt{frozen\_target})$, adds to environment, and audits kernel axioms.
  - Sentinel: `VERIFY_LIFTED_SENTINEL_OK`.

---

## 5. Predeclared Hypotheses & Falsification Criteria

### 5.1 Calibration Arm: Sequential Multi-Theorem Amortization (H1)
Evaluated via `run_calibration_family` in `tools/executor_harness.py`:
- Marginal Dividend: $\Delta_L^{(2)} \le 0.50 \times \Delta_D^{(2)}$
- Cumulative Amortization: $W_L(T_1 + T_2) < W_D(T_1 + T_2)$

### 5.2 Blind Arm: Discovery Feasibility (H2)
Evaluates discovery rate of valid representation stubs under 3600-second search ceiling across 3 drand-selected problems.

### 5.3 Negative Control: Protocol Integrity (H0)
Evaluated according to the pre-frozen Control Outcome Matrix in Section 2.3.

---

## 6. Execution Checklist & Pre-Freeze Gates

- [ ] **Gate 0:** Repository initialized at `https://github.com/VolMax-Studio/representation-lifting-s1` with checked-in Lake project.
- [ ] **Gate 1:** Mechanical nontriviality script executed on ProofNet-Verified (367 base items).
- [ ] **Gate 2:** Verbatim Lean 4 v4.34.0 compilation filter executed; `EXCLUDED_TOOLCHAIN_INCOMPATIBLE.tsv` generated.
- [ ] **Gate 3:** `POOL.tsv` compiled, sorted, and canonical SHA-256 published.
- [ ] **Gate 4:** Target drand round committed via `tools/drand_schedule.py`.
- [ ] **Gate 5:** Live API Smoke Test executed (`tools/smoke_test_executor.py`).
- [ ] **Gate 6:** Human Ratification by Ivan Nestorov prior to the scheduled publication timestamp of the drand round.

---

## 7. Protocol Amendment History

- **Amendment 0.1 $\to$ 0.2:** Added $+2$ future round offset to drand schedule; formalized exact target type equivalence via Lean kernel `isDefEq`; added Negative Control matrix.
- **Amendment 0.2 $\to$ 0.3:** Replaced text regex checking with pure Lean 4 kernel meta-checkers (`CheckBridge.lean`, `VerifyTarget.lean`); formalized discrete Role S and live API smoke test.
- **Amendment 0.3 $\to$ 0.4:** Corrected Identity Guard value-level definitional equality; added sequential dependent binder type matching; added representation layer axiom whitelist.
- **Amendment 0.4 $\to$ 0.5:** Formally recorded Identity Guard amendment to AND semantics; created `VerifyLifted.lean` with transitive constant dependency; bound $W_L$ to full assembled artifact; checked in pinned Lake manifest; established infrastructure resilience rules.
- **Amendment 0.5 $\to$ 0.6:**
  - Method Mode Deny-List Enforcement: machine-readable `admissibility/<case>.json` deny-lists.
  - Restoration of Primary Method vs. Secondary Ecosystem Modes.
  - Structural Lift Architecture: Role S defines specification, Role L authors proofs, verifier checks components.
  - Sequential Multi-Theorem Calibration State Machine (H1): initial `run_calibration_family`.
- **Amendment 0.6 $\to$ 0.7:**
  - Actual Mechanical Target Synthesis: `VerifyLifted.lean` constructs `synthesized_target` and validates with kernel axiom audit.
  - Real Cumulative Compilation & Token Accounting ($T_1 \to T_2$).
  - Transitive Module-Local Non-Circularity with `NameSet`.
  - Mathlib target statement corrections (`hn : 1 ≤ n` on Cassini).
- **Amendment 0.7 $\to$ 0.8:**
  - Module-provenance candidate declaration enumeration (`env.getModuleIdxFor? c = none`).
  - Namespace-escape adversarial tests (`root_aux_forbidden.lean`, `namespace_escape_forbidden.lean`, `root_aux_circular.lean`, `namespace_escape_circular.lean`).
  - Admissibility deny-list precision: removed `Nat.fib_add_two` from `admissibility/fibonacci.json`.
- **Amendment 0.8 $\to$ 0.9 (Current):**
  - **Candidate Module Isolation:** Completely decoupled candidate compilation into independent modules (`CandidateDModule.lean`, `CandidateSModule.lean`, `CandidateLModule.lean`). Eliminated all name exceptions, `isTrusted` allowlists, and string heuristics (`_aux`, `_eval`, `_root_`, `private`). Candidate declarations are identified strictly by module index (`idx(CandidateModule)`).
  - **Mandatory Kernel Replay (`leanchecker`):** Integrated built-in `leanchecker` to replay all candidate `.olean` files directly through the Lean 4 kernel before semantic verification, defeating `set_option debug.skipKernelTC true` and untyped environment mutations.
  - **Process & Filesystem Sandbox:** Added environment secret scrubbing, repository snapshot verification to prevent filesystem mutations outside temporary scratch directories, and static defense-in-depth scanning blocking `run_cmd`, `#eval`, `initialize`, `unsafe`, `elab`, `macro`, `syntax`, `set_option debug.*`, `@[implemented_by]`, `IO.FS`, `IO.Process`, and `VerifierTrustCore`.
  - **Comprehensive Adversarial Fixtures:** Verified fail-closed enforcement across 5 dedicated fixtures: `aux_escape_forbidden.lean`, `aux_escape_circular.lean`, `skip_kernel_tc.lean`, `run_cmd_meta_cheat.lean`, and `run_cmd_fs_write.lean`.
