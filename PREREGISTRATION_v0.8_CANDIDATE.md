# representation-lifting-s1: PREREGISTRATION v0.8 CANDIDATE
**Status:** READY FOR CLAUDE GATE / HUMAN RATIFICATION (SUPERSEDES v0.1 `254e06d8…`, v0.2 `4fdc0bf4…`, v0.3 `da532b0e…`, v0.4 `bdc5c76e…`, v0.5 `64e6cde8…`, v0.6 `ecb31e42…`, AND v0.7 `4f12eae5…`)  
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

## 3. Evaluation Regimes: Method Mode vs. Ecosystem Mode

### 3.1 Primary Regime: Method Mode (Machine-Readable Deny-Lists & Provenance Identification)
Method Mode is the **primary experimental condition**. It evaluates the autonomous capacity of the agent to discover and formalize representations and proofs from first principles, rather than querying terminal pre-packaged Mathlib theorems that trivialize the target.

1. **Machine-Readable Deny-Lists (`admissibility/<case>.json`):**
   - Explicit JSON declarations specifying fully qualified constant names forbidden from reference:
     - `admissibility/fibonacci.json`: Prohibits terminal shortcuts `Int.fib_succ_mul_fib_pred_sub_fib_sq`, `Nat.fib_add`, `Nat.fib_gcd`. Note: `Nat.fib_add_two` is the foundational recurrence ($F(n+2) = F(n) + F(n+1)$, marked `@[simp]`), not a terminal goal shortcut, and is explicitly permitted.
     - `admissibility/pell.json`: Prohibits `Pell.Solution₁` and all child projection/multiplication lemmas (`Pell.Solution₁.x_mul`, `y_mul`, `mul`, `pow`, `x_pow`, `y_pow`, `x_pow_pos`).
     - `admissibility/roots_of_unity.json`: Prohibits `IsPrimitiveRoot.geom_sum_eq_zero`.
   - **Mechanical Admissibility Rule:**
     $$\text{Forbidden}(T) = \{\text{Mathlib declarations whose type is defeq with } T\} \cup \{\text{ratified near-equivalent terminal shortcuts}\}.$$

2. **Declaration Provenance via Lean Environment Module Indexing (v0.8):**
   - Candidate authorship is decoupled completely from namespace strings or naming conventions.
   - A declaration $c$ is defined as candidate-authored if and only if it was introduced during the current compilation unit and does not belong to the trusted verifier core:
     $$\boxed{ \text{CandidateDecl}(c) \iff \text{env.getModuleIdxFor?}(c) = \text{none} \land \neg \text{isTrusted}(c) }$$
   - `isTrusted(c)` covers only:
     - `VerifierTrustCore` (the verifier functions and synthetic targets)
     - `frozen_target` (the immutable problem statement)
     - Pre-frozen specification symbols in Role L (`LiftDom`, `LiftCod`, `liftT`, `LiftedClaim`, `BridgeProp`, `invariant`)
     - Lean internal compiler elaboration artifacts (`_eval`, `_unsafe_rec`, `_aux`).
   - Under this definition, all attempts to escape namespaces (via `theorem _root_.aux ...`, custom namespaces, closed namespaces `end CandidateExecutor ... namespace CandidateExecutor`, or `private` definitions) remain strictly identified as candidate declarations.
   - **Fail-Closed Harness Protection:** Candidate source code is statically scanned for `\bVerifierTrustCore\b`. Any occurrence immediately aborts with `FAIL_CLOSED: Candidate code attempts to spoof verifier trust core`.

3. **Prefix and Exact Deny Scanning:**
   - Any candidate declaration $c$ referencing a prohibited constant $p$ ($p = c \lor p.\text{isPrefixOf}(c)$) in its type or value fails closed with `FORBIDDEN_METHOD_MODE_CONSTANT`.

### 3.2 Secondary Regime: Ecosystem Mode (Sensitivity Baseline)
Ecosystem Mode serves as a secondary sensitivity analysis:
- All Mathlib lemmas are unconstrained.
- Evaluates the extent to which library coverage biases formalization efficiency when pre-packaged domain abstractions are available.

---

## 4. Operational Protocols: Search, Gate, & Structural Lift

### 4.1 Mechanical Representation-Search Protocol (Role S)
For each blind problem:
1. **Search Executor Role (S):**
   - **Pinned Identity:** `claude-sonnet-4-6` (Primary) / `gpt-5.6-sol` (Replication).
   - **Search Budget:** Exactly 3600 seconds wall-clock time, capped at 15 turns in `tools/executor_harness.py`.
   - **Tool Access:** Read target statement, read admissibility manifest, write candidate stub file, execute Lean compiler diagnostics.
2. **Deliverable Requirement:** The search phase produces an executable Lean stub file conforming to the structural representation specification interface:
   ```lean
   -- Generic representation types
   abbrev LiftDom := ...
   abbrev LiftCod := ...
   
   -- Representation map
   def liftT : LiftDom → LiftCod := ...
   
   -- Invariant or target structure
   def invariant : LiftCod → ... := ...
   
   -- Closed lifted proposition (proof-free)
   def LiftedClaim : Prop := ...
   
   -- Proof-free Bridge Property linking target and LiftedClaim (zero sorryAx)
   def BridgeProp : Prop :=
     ∀ (vars...), original_claim ↔ lifted_claim
   ```
3. **Pure Lean Meta-Checker Verification (`tools/CheckBridge.lean`):**
   - **Environment Requirement:** Verified strictly using the checked-in Lake project via `lake env lean`.
   - **Module-Provenance Candidate Enumeration:** Discovers all candidate declarations introduced in the stub via `env.getModuleIdxFor? c = none`.
   - **Comprehensive Representation Axiom Audit:** All candidate declarations in environment must depend ONLY on $\{\texttt{propext}, \texttt{Classical.choice}, \texttt{Quot.sound}\}$ (zero `sorryAx` anywhere).
   - **Identity Guard (AND semantics):**
     $$\text{isDefEq}(\text{LiftDom}, \text{LiftCod}) \land \text{isDefEq}(\text{liftT}, @\text{id LiftDom})$$
     If both hold $\implies$ fails with **`LIFT-NOT-FOUND / IDENTITY_GUARD`**.
   - **Linkage Verification:** Asserts `BridgeProp` conclusion is a non-tautological equivalence connecting target conclusion to `LiftedClaim` conclusion, and contains `liftT`.
   - **Sentinel Enforcement:** Requires exit code 0 and exact terminal line `CHECK_BRIDGE_SENTINEL_OK`.

### 4.2 Structural Lift Architecture & Mechanical Target Synthesis (Role L, `tools/VerifyLifted.lean` & `tools/verify_lifted.sh`)
1. **Role S Frozen Prefix:** Role S declares `LiftDom`, `LiftCod`, `liftT`, `LiftedClaim : Prop`, and `BridgeProp : Prop`.
2. **Role L Scope:** Role L authors **ONLY**:
   - `preservation_bridge : BridgeProp`
   - `lifted_theorem : LiftedClaim`
3. **Mechanical Synthesis of Original Target Theorem:**
   - The executor does **not** author `executor_theorem`.
   - The trusted verifier (`VerifyLifted.lean`) detects the orientation of `BridgeProp` under the target telescope (`Iff.mpr` vs `Iff.mp`).
   - The verifier mechanically constructs the proof term:
     $$\texttt{fullProof} := \lambda \vec{x} \implies (\texttt{preservation\_bridge}\ \vec{x}).\text{mpr/.mp}\ (\texttt{lifted\_theorem}\ \vec{x})$$
   - Asserts $\text{type}(\texttt{fullProof}) \equiv_{\text{def}} \text{type}(\texttt{frozen\_target})$.
   - Adds $\texttt{VerifierTrustCore.synthesized\_target}$ directly into the environment and performs a strict kernel axiom audit ($A \subseteq \{\texttt{propext}, \texttt{Classical.choice}, \texttt{Quot.sound}\}$, zero `sorryAx`).
4. **Module-Provenance Transitive Non-Circularity Audit (v0.8):**
   - Traverses the full transitive dependency closure of `lifted_theorem` across all local declarations ($\text{env.getModuleIdxFor?}(c) = \text{none} \land \neg\text{isTrusted}(c)$) using a `NameSet`.
   - Asserts: $\texttt{preservation\_bridge} \notin \text{Deps}^*(\texttt{lifted\_theorem})$.
   - Completely closes namespace-escape bypasses (e.g., `_root_.aux := preservation_bridge`, or escaped namespaces), triggering `CIRCULAR_LIFT_DEPENDENCY`.
5. **Sentinel Enforcement:** Requires exit code 0 and exact sentinel `VERIFY_LIFTED_SENTINEL_OK`.

---

## 5. Infrastructure Resiliency, Timeouts, & Metrics

### 5.1 Infrastructure Configuration (`tools/executor_config.json`)
- **Pinned Models:** `claude-sonnet-4-6` (Primary) and `gpt-5.6-sol` (Replication).
- **Output Token Ceiling:** 8192 tokens.
- **Request Timeout:** 600 seconds per request (eliminating request-timeout bias against longer Role L files).
- **Sampling Parameters:** Temperature pinned to 0.0.
- **Truncation Normalization:** Stop reasons of `max_tokens` (Anthropic) or `length` (OpenAI) are normalized to status **`OUTPUT_TRUNCATED`** with `output_truncated: true` logged in transcript.
- **Infrastructure Failure Governance (`INFRA_FAILURE`):** Up to 3 attempts per turn with backoff (5s, 15s) for retryable HTTP/network codes. Attempt exhaustion terminates with `INFRA_FAILURE` (`NOT_EVALUABLE_INFRA`).
- **Hard Wall-Clock Enforcement:** Deadlines enforced across all API and subprocess calls.

### 5.2 Metrics & Footprint Definition Alignment
For every problem evaluated, completion is recorded in the discrete registry:
$$O_{\text{completion}} \in \{\text{BOTH}, \text{L-ONLY}, \text{D-ONLY}, \text{NEITHER}, \text{NOT\_EVALUABLE\_INFRA}\}$$

Conditional strictly on $O_{\text{completion}} = \text{BOTH}$:
$$\Delta W_{\text{token}} = W_L - W_D$$

**Metric Definitions:**
- **For Direct Branch ($D$):**
  $$\boxed{ W_D = W(\text{all newly authored candidate declarations required for the proof}) }$$
  Evaluated across the candidate source file authored by Role D via `tools/count_lean_tokens.py`.
- **For Lifted Branch ($L$):**
  $$\boxed{ W_L = W(\text{frozen representation prefix} + \text{proved bridge} + \text{lifted theorem}) }$$
  Evaluated across the full assembled artifact via `tools/count_lean_tokens.py`.

---

## 6. Predeclared Hypotheses & Falsification Criteria

### 6.1 Calibration Arm: Sequential Multi-Theorem Amortization (H1)
Evaluated via `run_calibration_family(family_name, model_id)` in `tools/executor_harness.py`:
1. **Direct Branch:**
   - Role D proves $T_1 \implies W_D(T_1)$.
   - $D_1$ is compiled as an immutable frozen module prefix alongside $D_2 \implies W_D(T_1 + T_2) = \text{tokens}(D_1 + D_2)$.
   - Marginal direct cost: $\Delta_D^{(2)} = W_D(T_1 + T_2) - W_D(T_1) \ge 0$.
2. **Lifted Branch:**
   - Role S discovers representation on $T_1 \implies S_1$.
   - Role L proves $T_1$ with $S_1$ prefix $\implies W_L(T_1) = W(S_1 + L_1)$.
   - Representation core is frozen; Role S defines fresh specification $S_2$ for $T_2$; Role L proves $T_2$ with $S_{\text{core}} + L_{1\text{ helpers}} + S_2 \implies W_L(T_1 + T_2) = \text{tokens}(S_1 + L_1 + S_2 + L_2)$.
   - Marginal lifted cost: $\Delta_L^{(2)} = W_L(T_1 + T_2) - W_L(T_1) \ge 0$.
3. **Primary Amortization Hypothesis (H1):**
   - **Marginal Dividend:**
     $$\Delta_L^{(2)} \le 0.50 \times \Delta_D^{(2)}$$
   - **Cumulative Amortization:**
     $$W_L(T_1 + T_2) < W_D(T_1 + T_2)$$

### 6.2 Blind Arm: Discovery Feasibility (H2)
Across the 3 drand-selected blind problems:
- Evaluates the rate of `LIFT-FOUND` vs. `LIFT-NOT-FOUND`.
- Records $O_{\text{completion}}$ across all 3 cases.

### 6.3 Negative Control: Protocol Integrity (H0)
Evaluated according to the pre-frozen Control Outcome Matrix in Section 2.3.

---

## 7. Execution Checklist & Pre-Freeze Gates

- [ ] **Gate 0:** Repository initialized at `https://github.com/VolMax-Studio/representation-lifting-s1` with checked-in Lake project (`lean-toolchain`, `lakefile.toml`, `lake-manifest.json`).
- [ ] **Gate 1:** Mechanical nontriviality script (`tools/nontriviality_filter.sh`) executed on ProofNet-Verified (367 base items).
- [ ] **Gate 2:** Verbatim Lean 4 v4.34.0 compilation filter executed; `EXCLUDED_TOOLCHAIN_INCOMPATIBLE.tsv` generated with exact compiler diagnostics.
- [ ] **Gate 3:** `POOL.tsv` compiled, sorted, and canonical SHA-256 published.
- [ ] **Gate 4:** Target drand round committed via `tools/drand_schedule.py` ($r_{\text{scheduled}} = \lfloor (u - 1692803367)/3 \rfloor + 2$ with $u = t_{\text{pub}} + 600$).
- [ ] **Gate 5:** Live API Smoke Test executed (`tools/smoke_test_executor.py`), recording HTTP 200 and exact model ID match into `tools/smoke_test_receipt.json`.
- [ ] **Gate 6:** Human Ratification by Ivan Nestorov prior to the scheduled publication timestamp of the drand round.

---

## 8. Protocol Amendment History

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
- **Amendment 0.7 $\to$ 0.8 (Current):**
  - **Declaration Provenance via Lean Environment Module Indexing:** Decoupled candidate declaration identification completely from namespace prefixes or string names. Replaced `isCandidateDecl` with `env.getModuleIdxFor? c = none && !isTrusted(c)`. All declarations introduced in the current compilation file are audited regardless of whether they are declared in `_root_`, closed namespaces, custom namespaces, or as `private`.
  - **Namespace-Escape Vulnerability Closure:** Added 4 adversarial test fixtures verifying that `_root_.aux` and `end CandidateExecutor ... namespace CandidateExecutor` escapes fail closed against both Method Mode deny-lists and transitive circularity checks (`root_aux_forbidden.lean`, `namespace_escape_forbidden.lean`, `root_aux_circular.lean`, `namespace_escape_circular.lean`).
  - **Admissibility Deny-List Precision:** Removed `Nat.fib_add_two` from `admissibility/fibonacci.json`. `Nat.fib_add_two` is the foundational inductive recurrence $F(n+2) = F(n) + F(n+1)$, not a terminal target shortcut. Retained terminal shortcuts `Int.fib_succ_mul_fib_pred_sub_fib_sq`, `Nat.fib_add`, and `Nat.fib_gcd`.
  - **Fail-Closed Verifier Trust Core Guard:** Added harness static analysis rejecting candidate code referencing `\bVerifierTrustCore\b` to prevent spoofing of trusted verifier declarations.
