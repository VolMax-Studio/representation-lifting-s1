# representation-lifting-s1: PREREGISTRATION v0.4 CANDIDATE
**Status:** READY FOR BYTE-LEVEL TEXT/PROCEDURE GATE (SUPERSEDES v0.1 `254e06d8…`, v0.2 `4fdc0bf4…`, AND v0.3 `da532b0e…`)  
**Author / Principal Investigator:** Ivan Nestorov  
**Target Toolchain:** Lean 4 (v4.34.0) / Mathlib v4.34.0  
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
│ • Pell (Fund. unit + Product)   │        │ • Mechanical nontriviality      │        │ • Frozen Gnomon Stub            │
│ • Roots of Unity (Geom sum + Re)│        │ • Verbatim compile on 4.34      │        │ • Symmetric outcome matrix      │
│ Evaluates: Symmetric marginal   │        │ • drand quicknet (N=3 cases)    │        │ • Falsifies metric bias         │
│            amortization (T1, T2)│        │ Evaluates: Discovery & Step 1   │        │ Evaluates: Scoring integrity    │
└─────────────────────────────────┘        └─────────────────────────────────┘        └─────────────────────────────────┘
```

### 2.1 Calibration-Family Arm (Symmetric Amortization & Marginal Cost)
Evaluates whether establishing an explicit representation layer ($T: \text{LiftDom} \to \text{LiftCod}$) and preservation bridge incurs an initial setup footprint penalty on theorem $T_1$, but yields a significant marginal footprint reduction on a subsequent related theorem $T_2$ from the same family.

**Symmetric Execution Rule:**  
Both branches ($L$ and $D$) execute $T_2$ in the **same source file** immediately following their verified $T_1$ proof. Both branches have identical rights to reuse their own definitions, intermediate lemmas, and infrastructure established during $T_1$.

**Frozen Lean Calibration Statements:**

1. **Fibonacci Family:**
   - $T_1$ (Cassini identity):
     ```lean
     theorem fib_cassini (n : ℕ) :
         (Nat.fib (n + 1) : ℤ) * (Nat.fib (n - 1) : ℤ) - (Nat.fib n : ℤ)^2 = (-1)^n
     ```
   - $T_2$ (Additive formula):
     ```lean
     theorem fib_add (m n : ℕ) :
         Nat.fib (m + n + 1) = Nat.fib m * Nat.fib n + Nat.fib (m + 1) * Nat.fib (n + 1)
     ```
   - *Lifted Representation:* Matrix ring $M_2(\mathbb{Z})$ with generator $Q = \begin{pmatrix} 1 & 1 \\ 1 & 0 \end{pmatrix}$.

2. **Pell Family:**
   - $T_1$ (Solution composition):
     ```lean
     theorem pell_solution_mul (x₁ y₁ x₂ y₂ : ℤ)
         (h₁ : x₁^2 - 2 * y₁^2 = 1) (h₂ : x₂^2 - 2 * y₂^2 = 1) :
         (x₁ * x₂ + 2 * y₁ * y₂)^2 - 2 * (x₁ * y₂ + x₂ * y₁)^2 = 1
     ```
   - $T_2$ (Power closure / second solution):
     ```lean
     theorem pell_solution_pow2 (x y : ℤ) (h : x^2 - 2 * y^2 = 1) :
         (x^2 + 2 * y^2)^2 - 2 * (2 * x * y)^2 = 1
     ```
   - *Lifted Representation:* Ring of integers $\mathbb{Z}[\sqrt{2}]$ via `Zsqrtd 2`.  
     *(Admissibility note: Mathlib's pre-packaged `Pell.Solution₁` group theorems are prohibited in Method Mode for both branches; the lifted branch must construct its representation explicitly).*

3. **Roots of Unity Family:**
   - $T_1$ (Trigonometric cosine vanishing sum):
     ```lean
     theorem cos_sum_roots_of_unity (n : ℕ) (hn : 2 ≤ n) :
         ∑ k ∈ Finset.range n, Real.cos (2 * Real.pi * k / n) = 0
     ```
   - $T_2$ (Trigonometric sine vanishing sum):
     ```lean
     theorem sin_sum_roots_of_unity (n : ℕ) (hn : 2 ≤ n) :
         ∑ k ∈ Finset.range n, Real.sin (2 * Real.pi * k / n) = 0
     ```
   - *Lifted Representation:* Cyclotomic field / primitive complex roots of unity $\zeta_n = e^{2\pi i / n}$.

### 2.2 Blind Transfer Arm (Discovery Feasibility)
Evaluates whether a representation-first search can discover a valid representation and preservation bridge on externally sourced problems without hindsight, and records the resulting completion outcomes.
- **Broader Scope Declaration:** Because the external pool is constructed from the complete ProofNet-Verified corpus without subjective mathematical domain filtering, it encompasses undergraduate analysis, topology, and abstract algebra. Under the 60-minute representation search ceiling, a high frequency of `LIFT-NOT-FOUND` is an expected, legitimate descriptive finding of H2 (quantifying the empirical boundary of automatic representation discovery), rather than an experimental failure.
- Does **not** assert claims regarding $T_2$ amortization (as external benchmark items do not come paired with predetermined structural sibling theorems).

### 2.3 Negative Control Arm (Scoring Integrity Check)
- **Target Statement:**
  ```lean
  theorem sum_odd_sq (n : ℕ) :
      ∑ k ∈ Finset.range n, (2 * k + 1) = n^2
  ```
- **Direct Path:** Direct induction or basic arithmetic summation over `Finset.range`.
- **Lifted Path:** Pre-frozen gnomon decomposition stub (`calibration/ControlGnomonStub.lean` committed before execution).
- **Pre-frozen Control Outcome Matrix:**
  | Observed Outcome | Formalization Footprint | Verdict | Operational Action |
  |---|---|---|---|
  | `D-ONLY` | N/A | **`CONTROL_PASS`** | Integrity confirmed; direct wins on flat problem. |
  | `BOTH` | $W_D < W_L$ | **`CONTROL_PASS`** | Integrity confirmed; metric correctly penalizes unnecessary lift. |
  | `L-ONLY` | N/A | **`COMPROMISED`** | Protocol failure; direct branch starved or broken. |
  | `BOTH` | $W_L \le W_D$ | **`COMPROMISED`** | Protocol failure; metric possesses structural bias toward lifting. |
  | `NEITHER` | N/A | **`CONTROL_INCONCLUSIVE`**| Both failed; raw data preserved, no method-level conclusion. |

---

## 3. External Pool Sampling & drand Selection Protocol

### 3.1 Source Corpus & Filtering Pipeline
1. **Base Corpus:** `ProofNet-Verified` (commit-pinned repository, containing 367 source cases).
2. **Canonical ProofNet Bundle:**  
   To preserve full elaborability in Lean 4 without manual syntax parsing, each problem entry is assembled canonicalized as:
   $$\text{Canonical Target} = \text{header} + \text{helper} + \text{frozen\_target declaration}$$
   All `import` statements are automatically hoisted to the head of the file during verification.
3. **Elimination of Subjective Domain Filter:**  
   Because ProofNet-Verified lacks an authoritative `NumberTheory`/`Algebra` column in its published schema, **no manual domain classification is permitted**. All 367 cases enter the mechanical pipeline. If a topological or analytic problem fails to yield a representation lift, that failure is recorded as an authentic `LIFT-NOT-FOUND`.
4. **Mechanical Nontriviality Filter:**  
   Each candidate theorem is tested against 4 independent tactics under a strict heartbeat ceiling:
   - `by rfl`
   - `by decide`
   - `by linarith`
   - `by ring`
   - Parameter: `set_option maxHeartbeats 200000`.
   - Implemented via a single hashed script (`tools/nontriviality_filter.sh`). Any problem solved by any of the 4 tactics is excluded.
5. **Verbatim Toolchain Compilation Filter:**
   - Every surviving theorem statement must elaborate and compile **verbatim** on the pinned toolchain (`Lean 4 v4.34.0` / `Mathlib v4.34.0`) without editing any statement line, import, or type signature.
   - Any candidate failing verbatim compilation is assigned to `EXCLUDED_TOOLCHAIN_INCOMPATIBLE.tsv` with compiler error diagnostics and excluded prior to pool serialization.
6. **Training Contamination Disclaimer:**
   > *The corpus is public and prior model exposure cannot be excluded or audited. Fresh contexts prevent conversational leakage between experimental branches; they do not establish training-data decontamination.*

### 3.2 Pool Exhaustion & Insufficient Pool Rule
The filter pipeline runs strictly sequentially:
$$367 \xrightarrow{\text{nontriviality}} N_{\text{nontrivial}} \xrightarrow{\text{compile 4.34}} N_{\text{compile}} = N$$

If the surviving pool count satisfies $N < 3$ (or in the extreme $N = 0$):
- The Blind Transfer Arm immediately terminates with status **`INSUFFICIENT_POOL`**.
- No fallback, loose filtering, domain expansion, statement porting, or alternative benchmarks are permitted.
- All intermediate counts ($367, N_{\text{nontrivial}}, N_{\text{compile}}$) and the complete list of excluded items with compiler logs are published.
- The Calibration-Family Arm and Negative Control Arm proceed completely independently.

### 3.3 Canonical Pool Construction
- All passing candidate rows are sorted in ascending lexicographical order by stable source identifier.
- Formatted as `POOL.tsv` (UTF-8, LF line endings, header row excluded for indexing).
- Total candidate count: $N$.
- The exact SHA-256 hash of `POOL.tsv` and $N$ must be committed and published **prior** to the scheduled drand beacon round.

### 3.4 drand Quicknet Specification & Deterministic Sampling
1. **Network Root-of-Trust:**
   - Chain: `quicknet` (drand mainnet unchained 3-second network).
   - Chain Hash: `52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971`.
   - Genesis Time: `1692803367` (Unix epoch).
   - Period: `3` seconds.
2. **Guaranteed Future Round Formula:**  
   To prevent selecting a round that has already been published at timestamp $t_{\text{pub}}$, an immutable safety gap of $600$ seconds is enforced:
   $$u = t_{\text{pub}} + 600$$
   The scheduled round is computed via `tools/drand_schedule.py`:
   $$\boxed{ r_{\text{scheduled}} = \left\lfloor \frac{u - 1692803367}{3} \right\rfloor + 2 }$$
   
   **Structural Invariant:**  
   $$\text{time}(r_{\text{scheduled}} - 1) \le u < \text{time}(r_{\text{scheduled}}) \quad \text{where} \quad \text{time}(r) = 1692803367 + (r - 1) \times 3$$
   *(The $+2$ offset strictly guarantees that the selected round is published strictly after $u$, even if $u$ coincides exactly with a round boundary. Fully verified by regression tests in `tests/test_drand_schedule.py`).*

3. **Randomness Value $R$:**  
   $R = \text{SHA-256}(\text{signature})$ of round $r_{\text{scheduled}}$, verified via BLS verification against the quicknet public key.
4. **Rejection-Sampling Algorithm (`tools/select_indices.py`):**  
   Selection of 3 distinct indices $i \in \{0, 1, \dots, N-1\}$ proceeds deterministically without modulo bias via rejection sampling.

---

## 4. Operational Protocols: Search, Gate, & Execution

### 4.1 Mechanical Representation-Search Protocol (`LIFT-NOT-FOUND`)
For each blind problem:
1. **Search Executor Role (S):**
   - **Pinned Identity:** `claude-sonnet-4-6` (Primary) / `gpt-5.6-sol` (Replication).
   - **Search Budget:** Exactly 3600 seconds wall-clock time, capped at 15 turns in `tools/executor_harness.py`.
   - **Tool Access:** Read target statement, read admissibility manifest, write candidate stub file, execute Lean compiler diagnostics. Zero access to external search or human assistance.
2. **Deliverable Requirement:** The search phase must produce an executable Lean stub file conforming to the generalized representation interface:
   ```lean
   -- Generic representation types
   abbrev LiftDom := ...
   abbrev LiftCod := ...
   
   -- Representation map
   def liftT : LiftDom → LiftCod := ...
   
   -- Invariant or target structure
   def invariant : LiftCod → ... := ...
   
   -- Preservation bridge (sorry allowed ONLY here)
   theorem preservation_bridge ... : ... ↔ ... := by sorry
   ```
3. **Pure Lean Meta-Checker Verification (`tools/CheckBridge.lean`):**
   The candidate stub is verified directly inside the Lean 4 kernel/MetaM via `tools/check_bridge.py`:
   - **Compilation:** The entire stub must elaborate without error on the pinned toolchain.
   - **Representation Layer Axiom Whitelist:**  
     Transitive axioms of `LiftDom`, `LiftCod`, `liftT`, and any helper definitions must satisfy:
     $$A_{\text{rep}} \subseteq \{\texttt{propext}, \texttt{Classical.choice}, \texttt{Quot.sound}\}$$
     *(Zero `sorryAx` and zero custom unproved axioms permitted in representation definitions).*
   - **Bridge Axiom Whitelist:**  
     $$A_{\text{bridge}} \subseteq \{\texttt{propext}, \texttt{Classical.choice}, \texttt{Quot.sound}, \texttt{sorryAx}\}$$
     *(Strictly `sorryAx` allowed in `preservation_bridge`).*
   - **Identity Guard (AND semantics):** Evaluates definitional equality in the Lean kernel:
     $$\text{isDefEq}(\text{LiftDom}, \text{LiftCod}) \land \text{isDefEq}(\text{liftT}, @\text{id LiftDom})$$
     If both domain/codomain are definitionally identical AND `liftT` is definitionally the identity function $\implies$ fails with **`LIFT-NOT-FOUND / IDENTITY_GUARD`**. (Tested and confirmed: same domain + non-id mapping passes; same domain + id mapping fails).
   - **Sequential Dependent Binder Type Matching:**
     1. Uses `forallTelescope` on `frozen_target` and `preservation_bridge`.
     2. Asserts binder count matches identically.
     3. For each binder index $i$, verifies $t_{\text{type}} \equiv_{\text{def}} b_{\text{type}}[\vec{b}_{<i} \mapsto \vec{t}_{<i}]$. Rejects mismatched hypotheses (e.g. $2 \le n$ vs $100 < n$) or mismatched dependent binders.
   - **Target Linkage Verification:**
     1. Asserts the conclusion is an equivalence (`↔`).
     2. Asserts LHS and RHS are not syntactically tautological ($P \leftrightarrow P$).
     3. Asserts one side is definitionally equal (`isDefEq`) to the target conclusion.
     4. Asserts the other side contains an explicit constant reference (`Expr.const`) to `liftT`.
   - **Sentinel Enforcement:** Requires exit code 0 and exact terminal line `CHECK_BRIDGE_SENTINEL_OK`.  
   *(Fully verified and regression-tested across all 11 frozen fixtures in `tests/test_check_bridge.py`).*
4. **Outcome Assignment:**
   - Passes all checks: Canonicalized, SHA-256 hashed, locked, and passed to Executor L as `LIFT-FOUND`.
   - Any failure: Mechanically recorded as **`LIFT-NOT-FOUND`**. No human subjective adjudication.

### 4.2 Exact-Target Verification & Axiom Audit
To guarantee that branches prove literally the assigned target theorem:
1. **Pure Lean Meta-Checker (`tools/VerifyTarget.lean`):**
   Proof verification executes directly in the Lean kernel via `tools/verify_proof.sh`:
   $$\text{isDefEq}(\text{type}(\texttt{executor\_theorem}), \text{type}(\texttt{frozen\_target}))$$
   - Kernel definitional equality automatically resolves $\alpha$-renaming of bound variables, implicit binders, dependent $\Pi$-types, existentials, and equivalences without brittle text interpolation.
2. **Fail-Closed Axiom Audit:**
   Transitive axioms are extracted via `Lean.collectAxioms` and certified against the frozen whitelist:
   $$A_{\text{observed}} \subseteq \{\texttt{propext}, \texttt{Classical.choice}, \texttt{Quot.sound}\}$$
   Any proof depending on `sorryAx`, custom axioms, or unproved constants fails closed.
3. **Fail-Closed Scan:**
   Rejects forbidden tokens (`sorry`, `admit`, `native_decide`) prior to compilation.

### 4.3 Executor Specifications, Harness, & Pre-Freeze Smoke Test
1. **Pinned Model Identities (No In-Flight Fallbacks):**
   - **Primary Suite:** Anthropic `claude-sonnet-4-6` for S, D, and L.
   - **Replication Suite:** OpenAI `gpt-5.6-sol` for S, D, and L.
   - *Rule:* Pinned IDs are immutable. If an API endpoint is unavailable during the execution window, the run fails closed. A model migration requires a formal v0.5 candidate release, not an ambient fallback.
2. **Cryptographic Execution Harness (`tools/executor_harness.py`):**
   - Governs interaction turns, compiler feedback loop, and immutable logging.
   - **Binding Budgets:**
     - Role S: 3600 seconds wall-clock, max 15 interaction turns.
     - Role D: 10800 seconds wall-clock, max 30 interaction turns.
     - Role L: 10800 seconds wall-clock, max 30 interaction turns.
   - Termination occurs strictly upon verified completion, turn exhaustion, or wall-clock expiration.
3. **Context Isolation:**
   - **Direct ($D$):** Target statement + admissibility manifest. Zero stub or search access.
   - **Lifted ($L$):** Target statement + admissibility manifest + frozen `LIFT-FOUND` stub.
4. **Mandatory Pre-Freeze API Smoke Test (`tools/smoke_test_executor.py`):**
   Prior to human ratification (Gate 6), a live HTTP ping must be executed against both endpoints, verifying:
   $$\text{verified} = (\text{http\_status} == 200) \land (\text{returned\_model\_id} == \text{pinned\_model\_id})$$
   Recording verified accessibility into `tools/smoke_test_receipt.json`. Missing credentials or model mismatch fails the pre-freeze gate closed.

### 4.4 Immutable Admissibility Manifest
- **Method Mode (Primary):** Prohibits terminal target-equivalent library lemmas.
  - Calibration Fibonacci: Prohibits `Int.fib_succ_mul_fib_pred_sub_fib_sq` and `Nat.fib_gcd`.
  - Calibration Pell: Prohibits `Pell.Solution₁` generator theorems that solve the goal by definition.
  - Calibration Roots of Unity: Prohibits `IsPrimitiveRoot.geom_sum_eq_zero`.
- **Blind Manifest Gate:** Case-specific manifests are frozen **after** drand sampling but **prior** to launching proof attempts. Unforeseen lemmas are flagged as `PROTOCOL_AMBIGUITY` (original outcome stands; re-run strictly as sensitivity run).

---

## 5. Metrics & Outcome Evaluation

### 5.1 Primary Categorical Outcome
For every problem evaluated, completion is recorded in the discrete registry:
$$O_{\text{completion}} \in \{\text{BOTH}, \text{L-ONLY}, \text{D-ONLY}, \text{NEITHER}\}$$

- **`BOTH`:** Both branches successfully produced a verified proof of the literal target statement within the 3-hour budget.
- **`L-ONLY`:** The lifted branch completed verification; the direct branch timed out or failed verification.
- **`D-ONLY`:** The direct branch completed verification; the lifted branch timed out or failed verification.
- **`NEITHER`:** Neither branch completed verification. (Retained as a valid descriptive outcome; never dropped from reporting).

### 5.2 Primary Quantitative Metric: Formalization Footprint
Conditional **strictly** on $O_{\text{completion}} = \text{BOTH}$, the footprint differential is evaluated:
$$\Delta W_{\text{token}} = W_L - W_D$$

Where $W_{\text{token}}$ is the **normalized authored Lean lexical token count**:
- Evaluated via `tools/count_lean_tokens.py` implementing Lean's lexical grammar.
- Includes all newly authored code (for $L$: includes `bridge` + `representation` + `theorem`).
- Strips comments, blank lines, whitespace, and `import` lines.
- Invariant to formatting and whitespace variations.
- Verified against 5 golden test fixtures in `fixtures/`.

> **Metric Interpretation Disclaimer:**  
> *$W_{\text{token}}$ measures artifact size under a fixed authoring protocol; it is not interpreted as human effort, cognitive difficulty, or semantic proof complexity.*

### 5.3 Secondary Metrics
Recorded alongside $W_{\text{token}}$:
1. Number of newly introduced declarations / lemmas ($N_{\text{lemmas}}$).
2. Number of interactive tactic invocations ($N_{\text{tactics}}$).
3. Number of distinct Mathlib definitions referenced.
4. Total model / solver tokens consumed.
5. Elapsed wall-clock time to verification.

---

## 6. Predeclared Hypotheses & Falsification Criteria

### 6.1 Calibration Arm: Symmetric Amortization Hypothesis (H1)
For each predeclared family $\{T_1, T_2\}$ executed symmetrically in the same file:
- Marginal lifted footprint: $\Delta_L^{(2)} = W_L(T_1 + T_2) - W_L(T_1)$
- Marginal direct footprint: $\Delta_D^{(2)} = W_D(T_1 + T_2) - W_D(T_1)$

**Primary Amortization Hypothesis (H1):**
1. **Marginal Dividend:**
   $$\Delta_L^{(2)} \le 0.50 \times \Delta_D^{(2)}$$
2. **Cumulative Amortization:**
   $$W_L(T_1 + T_2) < W_D(T_1 + T_2)$$

**Descriptive Prediction (P1):**
- Setup Cost: $W_L(T_1) \ge W_D(T_1)$. (Recorded as a descriptive prediction of representation overhead, not a falsification criterion).

**Evaluation Rules for H1:**
- **Falsification of H1:** If $\Delta_L^{(2)} > 0.50 \times \Delta_D^{(2)}$ or if $W_L(T_1 + T_2) \ge W_D(T_1 + T_2)$, H1 is **REJECTED** for that family.
- **Incompletion Rule:** If either branch fails to verify $T_1$, H1 is categorized as **`NOT_EVALUABLE`** for that family.

### 6.2 Blind Arm: Discovery Feasibility (H2)
Across the 3 drand-selected blind problems:
- Evaluates the rate of `LIFT-FOUND` vs. `LIFT-NOT-FOUND`.
- Records $O_{\text{completion}}$ across all 3 cases.
- **Reporting Rule:** Reported as a descriptive case-series. No percentage "success rate" extrapolation will be asserted.

### 6.3 Negative Control: Protocol Integrity (H0)
Evaluated according to the pre-frozen Control Outcome Matrix in Section 2.3:
- If `CONTROL_PASS`: Experiment integrity confirmed.
- If `COMPROMISED`: Entire experiment is declared **INVALID (FAIL)** due to demonstrated structural bias.
- If `CONTROL_INCONCLUSIVE`: Raw data published without method-level assertion.

---

## 7. Execution Checklist & Pre-Freeze Gates

- [ ] **Gate 0:** Repository initialized at `https://github.com/VolMax-Studio/representation-lifting-s1`.
- [ ] **Gate 1:** Mechanical nontriviality script (`tools/nontriviality_filter.sh`) executed on ProofNet-Verified (367 base items).
- [ ] **Gate 2:** Verbatim Lean 4 v4.34.0 compilation filter executed; `EXCLUDED_TOOLCHAIN_INCOMPATIBLE.tsv` generated with exact compiler diagnostics.
- [ ] **Gate 3:** `POOL.tsv` compiled, sorted, and canonical SHA-256 published.
- [ ] **Gate 4:** Target drand round committed via `tools/drand_schedule.py` ($r_{\text{scheduled}} = \lfloor (u - 1692803367)/3 \rfloor + 2$ with $u = t_{\text{pub}} + 600$).
- [ ] **Gate 5:** Live API Smoke Test executed (`tools/smoke_test_executor.py`), recording HTTP 200 and model ID match into `tools/smoke_test_receipt.json`.
- [ ] **Gate 6:** Human Ratification by Ivan Nestorov prior to the scheduled publication timestamp of the drand round.
