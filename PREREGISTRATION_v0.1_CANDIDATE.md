# representation-lifting-s1: PREREGISTRATION v0.1 CANDIDATE
**Status:** READY FOR TEXT/PROCEDURE GATE (RESOLVED BLOCKERS v0.1 CANDIDATE)  
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
2. **Elimination of Subjective Domain Filter:**  
   Because ProofNet-Verified lacks an authoritative `NumberTheory`/`Algebra` column in its published schema, **no manual domain classification is permitted**. All 367 cases enter the mechanical pipeline. If a topological or analytic problem fails to yield a representation lift, that failure is recorded as an authentic `LIFT-NOT-FOUND`.
3. **Mechanical Nontriviality Filter:**  
   Each candidate theorem is tested against 4 independent tactics under a strict heartbeat ceiling:
   - `by rfl`
   - `by decide`
   - `by linarith`
   - `by ring`
   - Parameter: `set_option maxHeartbeats 200000`.
   - Implemented via a single hashed script (`tools/nontriviality_filter.sh`). Any problem solved by any of the 4 tactics is excluded.
4. **Verbatim Toolchain Compilation Filter:**
   - Every surviving theorem statement must elaborate and compile **verbatim** on the pinned toolchain (`Lean 4 v4.34.0` / `Mathlib v4.34.0`) without editing any statement line, import, or type signature.
   - Any candidate failing verbatim compilation is assigned to `EXCLUDED_TOOLCHAIN_INCOMPATIBLE.tsv` with compiler error diagnostics and excluded prior to pool serialization.
5. **Training Contamination Disclaimer:**
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
2. **Round Formula:**  
   Given publication timestamp $t_{\text{pub}}$ of the committed `POOL.tsv` hash, the target round is scheduled at least 60 minutes into the future:
   $$r_{\text{target}} = \left\lfloor \frac{t_{\text{target}} - 1692803367}{3} \right\rfloor + 1$$
3. **Randomness Value $R$:**  
   $R = \text{SHA-256}(\text{signature})$ of round $r_{\text{target}}$, verified via BLS verification against the quicknet public key.
4. **Rejection-Sampling Algorithm:**
   Selection of 3 distinct indices $i \in \{0, 1, \dots, N-1\}$ proceeds deterministically without modulo bias:

```python
import hashlib

def select_indices(R: bytes, N: int, count: int = 3) -> list[int]:
    selected = []
    j = 0
    limit = (2**256) - ((2**256) % N)
    
    while len(selected) < count:
        msg = b"representation-lifting-s1/v0.1\x00" + R + j.to_bytes(8, byteorder="big")
        H_j = hashlib.sha256(msg).digest()
        v_j = int.from_bytes(H_j, byteorder="big")
        j += 1
        
        if v_j >= limit:
            continue
            
        candidate_idx = v_j % N
        if candidate_idx not in selected:
            selected.append(candidate_idx)
            
    return selected
```

---

## 4. Operational Protocols: Search, Gate, & Execution

### 4.1 Mechanical Representation-Search Protocol (`LIFT-NOT-FOUND`)
For each blind problem:
1. **Search Budget:** Exactly 60 minutes wall-clock time.
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
3. **Mechanical Verification, Identity Guard, & Target Linkage:**
   - **Toolchain Compilation:** The stub must compile with zero errors on the pinned toolchain (`sorry` permitted strictly inside `preservation_bridge`).
   - **Identity Guard Check:** In an isolated environment, the stub is checked for definitional triviality:
     ```lean
     example : LiftDom = LiftCod := rfl
     example : liftT = id := rfl
     ```
     *Rule:* If the isolated identity check file elaborates without error, the lift is rejected as trivial $\implies$ recorded mechanically as **`LIFT-NOT-FOUND / IDENTITY_GUARD`**. If compilation fails (e.g. types differ or `liftT` is not definitionally `id`), the identity guard is **not** activated.
     > *The identity guard excludes definitionally identical lifts. It does not purport to decide whether every surviving representation is mathematically substantive.* Any vacuous but non-identity lift proceeds into execution and absorbs the setup penalty.
   - **Target Linkage Verification:**  
     To prevent disconnected bridges (e.g. `foo (liftT x) ↔ foo (liftT x)`), a Lean meta-check inspects `preservation_bridge`:
     1. Peels off all leading universal $\Pi$-binders of the target theorem and `preservation_bridge`.
     2. Verifies that one side of the resulting `Iff` ($\leftrightarrow$) is **definitionally equal** to the target theorem's conclusion.
     3. Verifies that the other side of the `Iff` contains the constant identifier `liftT`.
     If the bridge fails this linkage check $\implies$ recorded as **`LIFT-NOT-FOUND / UNLINKED_BRIDGE`**.
4. **Outcome Assignment:**
   - Compiles cleanly, passes Identity Guard, and passes Target Linkage: Canonicalized, SHA-256 hashed, locked, and passed to Executor L as `LIFT-FOUND`.
   - Any failure: Mechanically recorded as **`LIFT-NOT-FOUND`**. No human subjective adjudication.

### 4.2 Exact-Target Verification & Axiom Audit
To guarantee that branches prove literally the assigned target theorem:
1. **Literal Target Checker:**
   For every proof submitted by an executor (whether $D$ or $L$), an automated verification harness generates a verification wrapper:
   ```lean
   -- Auto-generated from POOL.tsv / frozen calibration spec
   example : <literal target statement> := executor_theorem
   ```
   Must elaborate with zero errors on the pinned toolchain.
2. **Axiom Audit:**
   The axiom profile extracted via kernel introspection must satisfy:
   $$A_{\text{observed}} \subseteq \{\texttt{propext}, \texttt{Classical.choice}, \texttt{Quot.sound}\}$$
   Any proof relying on `sorryAx`, custom axioms, or undefined constants is rejected as invalid (`FAILED_VERIFICATION`).
3. **Fail-Closed Verification Script:**
   Executed via `tools/verify_proof.sh`, replicating the fail-closed scanning standards of Rung B.

### 4.3 Executor Isolation & Fixed Effort Budget
1. **Context Isolation:**
   - **Direct Executor ($D$):** Operates in a fresh context containing only the target theorem statement and the admissibility manifest. Zero access to the search transcript, stub, or representation definitions.
   - **Lifted Executor ($L$):** Operates in a fresh context containing the target theorem statement, the admissibility manifest, and the frozen `LIFT-FOUND` stub file.
2. **Uniform Prompting:**
   - Neutral prompt text: *"Write a clear, maintainable Lean proof."*
   - Prompts must **never** instruct length or tactic minimization. Prompt SHA-256 is recorded in the execution manifest.
3. **Executor Specifications:**
   - **Primary Fixed Model:** Claude 3.5 Sonnet (pinned version in manifest).
   - **Replication Model:** GPT-4o (pinned version in manifest; executed independently as a preregistered replication series without pooling).
   - Sampling parameters: Fixed temperature (or recorded as "not user-configurable" if locked by API).
4. **Binding Effort Budget:**
   - Exactly **3 hours wall-clock time** per branch.
   - Wall-clock timeout is the single binding termination condition. (Model tokens, solver steps, and heartbeats are recorded strictly as secondary descriptive metrics).

### 4.4 Immutable Admissibility Manifest
- **Method Mode (Primary):** Prohibits terminal target-equivalent library lemmas.
  - Calibration Fibonacci: Prohibits `Int.fib_succ_mul_fib_pred_sub_fib_sq` and `Nat.fib_gcd`.
  - Calibration Pell: Prohibits `Pell.Solution₁` generator theorems that solve the goal by definition.
  - Calibration Roots of Unity: Prohibits `IsPrimitiveRoot.geom_sum_eq_zero`.
- **Blind Manifest Gate:**
  - Case-specific manifests are frozen **after** drand sampling but **prior** to launching proof attempts.
  - If an unforeseen lemma arises during execution that trivializes the target, it is flagged as `PROTOCOL_AMBIGUITY`; the original outcome stands, and any re-run is conducted strictly as a secondary sensitivity analysis.

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
- **Tokenization Mechanism:** Evaluated via a frozen Python tokenization script (`tools/count_lean_tokens.py`) that implements Lean's lexical grammar.
- **Inclusions:** Includes all newly authored code required by the branch (for $L$: includes `bridge` + `representation` + `theorem`).
- **Exclusions:** Strips all comments, blank lines, whitespace formatting, and `import` declarations.
- **Whitespace Invariance:** Formatting variations (e.g. indentation, line breaks, or multiple spaces) produce an identical token stream and identical count.
- **Golden Test Fixtures:**
  The repository commits a set of golden test fixtures (`fixtures/*.lean`) with pre-calculated expected token counts covering critical lexical edge cases:
  1. Nested block comments (`/- /- ... -/ -/`).
  2. Quoted identifiers (`«foo bar»`).
  3. Unicode mathematical symbols.
  4. String literals containing comment markers (`"text -- not a comment"`).
  5. String literals containing escaped quotes (`"text \"escaped\""`).

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
- [ ] **Gate 4:** Target drand round committed based on publication timestamp ($r_{\text{target}}$ on `quicknet`).
- [ ] **Gate 5:** Case-specific admissibility manifests, neutral prompts, tokenization script, and golden test fixtures committed and hashed.
- [ ] **Gate 6:** Human Ratification by Ivan Nestorov prior to the scheduled publication timestamp of the drand round.
