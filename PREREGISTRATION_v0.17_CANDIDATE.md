# representation-lifting-s1: PREREGISTRATION v0.17 CANDIDATE
**Status:** ARCHITECTURE + ANALYSIS + SELECTION CUSTODY + EXTERNAL ANCHOR CONTRACT FROZEN / READY FOR PRE-RANDOMNESS GATES (SUPERSEDES v0.1 `254e06d8…`, v0.2 `4fdc0bf4…`, v0.3 `da532b0e…`, v0.4 `bdc5c76e…`, v0.5 `64e6cde8…`, v0.6 `ecb31e42…`, v0.7 `4f12eae5…`, v0.8 `6701f8f2…`, v0.9 `ee8c2dab…`, v0.10 `cd49146a…`, v0.11 `66558238…`, v0.12 `364dec3a…`, v0.13 `84f36cb3…`, v0.14 `114a563f…`, v0.15 `2aa3d9d1…`, AND v0.16 `b3d37f9e…`)  
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
│ • Pell (Fund. unit + Product)   │        │ • Mechanical nontriviality      │        │ • Frozen Gnomon Stub            │
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
     `theorem fibonacci_t1 (n : ℕ) (hn : 1 ≤ n) : fib (n + 1) * fib (n - 1) - (fib n)^2 = (-1)^n`
   - $T_2$ (Additive convolution):
     `theorem fibonacci_t2 (m n : ℕ) : fib (m + n + 1) = fib (m + 1) * fib (n + 1) + fib m * fib n`
2. **Pell Family (`calibration/pell_t1.lean`, `calibration/pell_t2.lean`):**
   - $T_1$ (Fundamental solution existence for $d = 2$):
     `theorem pell_t1 : ∃ x y : ℕ, x > 0 ∧ y > 0 ∧ x^2 - 2 * y^2 = 1`
   - $T_2$ (Multiplicative product of solutions):
     `theorem pell_t2 (x₁ y₁ x₂ y₂ : ℕ) (h₁ : x₁^2 - 2*y₁^2 = 1) (h₂ : x₂^2 - 2*y₂^2 = 1) : (x₁*x₂ + 2*y₁*y₂)^2 - 2*(x₁*y₂ + y₁*x₂)^2 = 1`
3. **Roots of Unity Family (`calibration/roots_of_unity_t1.lean`, `calibration/roots_of_unity_t2.lean`):**
   - $T_1$ (Geometric sum vanishing on non-trivial primitive roots):
     `theorem roots_of_unity_t1 (n : ℕ) (hn : 2 ≤ n) (ζ : ℂ) (hζ : IsPrimitiveRoot ζ n) : ∑ i ∈ Finset.range n, ζ^i = 0`
   - $T_2$ (Cosine projection / Real part):
     `theorem roots_of_unity_t2 (n : ℕ) (hn : 2 ≤ n) (ζ : ℂ) (hζ : IsPrimitiveRoot ζ n) : ∑ i ∈ Finset.range n, (ζ^i).re = 0`

---

### 2.2 Blind Transfer Arm (External Discovery & Generalization)
Evaluates whether Role S can discover a valid representation stub on three theorem statements drawn blindly from the ProofNet-Verified pool via drand quicknet random beacon.

- **Candidate Pool Source:** ProofNet-Verified (367 base formal theorems).
- **Mechanical Exclusion Criteria:**
  1. `tools/nontriviality_filter.sh`: Excludes one-line tactic trivialities (`by rfl`, `by decide`, `by linarith`, `by ring`).
  2. Pinned Toolchain Compatibility: Verbatim elaboration check under Lean 4 v4.34.0.
- **Candidate Pool Frozen Artifact:** `POOL.tsv` (sorted lexicographically by ProofNet ID; canonical SHA-256 published prior to drand round).
- **Deterministic Rejection-Sampling Formula (`tools/select_indices.py`):**  
  To eliminate modulo bias and guarantee uniform selection over pool size $N = |P|$, indices are sampled via domain-separated SHA-256 with rejection sampling:
  $$H_j = \operatorname{SHA256}(\texttt{"representation-lifting-s1/v0.1\textbackslash0"} \parallel R \parallel \operatorname{uint64be}(j))$$
  $$v_j = \operatorname{uint256be}(H_j)$$
  $$L = 2^{256} - (2^{256} \bmod N)$$
  If $v_j \ge L$, reject $v_j$; otherwise candidate index $i = v_j \bmod N$. If $i \notin \text{selected}$, append $i$. Increment counter $j \gets j + 1$ and repeat until $|\text{selected}| = 3$.
- **Future Beacon Commitment:** drand quicknet (`https://api.drand.sh/52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971`, genesis: 1692803367, period: 3s) committed at +2 future round offset via `tools/drand_schedule.py`.

---

### 2.3 Negative Control Arm (Scoring Integrity & Bias Falsification)
Evaluates whether the formalization footprint metric and harness scoring infrastructure possess a false positive bias toward representation lifting on a flat theorem that does not mathematically benefit from representation lifting.

- **Target Statement (`calibration/control_sum_odd.lean`):**
  ```lean
  theorem control_sum_odd (n : ℕ) : ∑ k ∈ Finset.range n, (2 * k + 1) = n^2
  ```
- **Direct Path:** Direct arithmetic / inductive summation over `Finset.range`.
- **Lifted Path:** Pre-frozen gnomon decomposition stub (`calibration/ControlGnomonStub.lean` committed before execution). Role S is skipped; Role L receives the pre-committed stub.
- **Execution Driver:** `run_control_case` in `tools/executor_harness.py`, subject to identical branch non-persistence and memory-only D custody.
- **Pre-Frozen Control Decision Matrix:**

| Observed Outcome ($O_{\text{completion}}$) | Footprint Condition | Verdict | Operational Action & Governance Effect |
|---|---|---|---|
| `D-ONLY` | N/A | **`CONTROL_PASS`** | Integrity confirmed; direct wins on flat problem. |
| `BOTH` | $W_D < W_L$ | **`CONTROL_PASS`** | Integrity confirmed; metric correctly penalizes unnecessary representation lifting. |
| `L-ONLY` | N/A | **`COMPROMISED`** | Protocol failure; direct branch starved or broken. **Veto active: Methodological conclusions of H1 and H2 completely invalidated.** |
| `BOTH` | $W_L \le W_D$ | **`COMPROMISED`** | Protocol failure; metric possesses structural bias toward lifting. **Veto active: Methodological conclusions of H1 and H2 completely invalidated.** |
| `NEITHER` | N/A | **`CONTROL_INCONCLUSIVE`**| Both branches failed; raw data preserved, no positive method-level claim may be asserted. |
| Missing Control Receipt | N/A | **`CONTROL_MISSING`** | Control run omitted. **Veto active: Methodological conclusions of H1 and H2 completely invalidated.** |
| Any `INFRA_FAILURE` | N/A | **`CONTROL_NOT_EVALUABLE_INFRA`** | Transport/infrastructure failure; control run aborted. |

> **Binding Negative Control Veto Rule:**  
> Execution of the negative control arm is **mandatory**. If the control receipt is omitted (`CONTROL_MISSING`) or if its verdict is **`COMPROMISED`**, the experimental instrument is declared structurally invalid. The automated analysis pipeline (`tools/analyze.py`) immediately sets `veto_active: true` and marks all method-level conclusions of H1 and H2 as `INVALIDATED_CONTROL_MISSING` or `INVALIDATED_BY_CONTROL_VETO`.

---

## 3. External Pool Sampling, drand Selection Custody Protocol, & External Anchor Contract

### 3.1 Source Corpus & Filtering Pipeline
1. **Base Corpus:** `ProofNet-Verified` (commit-pinned repository, containing 367 source cases).
2. **Elimination of Subjective Domain Filter:**  
   Because ProofNet-Verified lacks an authoritative `NumberTheory`/`Algebra` column in its published schema, **no manual domain classification is permitted**. All 367 cases enter the mechanical pipeline. If a topological or analytic problem fails to yield a representation lift, that failure is recorded as an authentic `LIFT-NOT-FOUND`.
3. **Mechanical Nontriviality Filter:**  
   Each candidate theorem is tested against 4 independent tactics under a strict heartbeat ceiling: `by rfl`, `by decide`, `by linarith`, `by ring`. Implemented via `tools/nontriviality_filter.sh`. Any problem solved by any of the 4 tactics is excluded.
4. **Verbatim Toolchain Compilation Filter:**  
   Statements must compile verbatim under Lean 4 v4.34.0. Incompatible cases are logged to `EXCLUDED_TOOLCHAIN_INCOMPATIBLE.tsv`.

### 3.2 Pool Exhaustion & Insufficient Pool Rule
The filter pipeline runs strictly sequentially:
$$367 \xrightarrow{\text{nontriviality}} N_{\text{nontrivial}} \xrightarrow{\text{compile 4.34}} N_{\text{compile}} = N$$
If the surviving pool count satisfies $N < 3$ (or in the extreme $N = 0$):
- The Blind Transfer Arm immediately terminates with status **`INSUFFICIENT_POOL`**.
- No fallback, loose filtering, domain expansion, statement porting, or alternative benchmarks are permitted.
- The Calibration-Family Arm and Negative Control Arm proceed completely independently.

### 3.3 Scope and Boundary of Automated Analysis (`analyze.py`)

> **Boundary Statement:**  
> `analyze.py` deterministically reproduces the selection conditional on externally verified pool-timestamp and drand-BLS authenticity receipts. It does not itself establish those external facts.

The complete trust chain bridges the boundary between internal deterministic custody and external public trust anchors:

$$\boxed{ \text{POOL.tsv} \xrightarrow{\text{timestamp proof}} \text{pool\_anchor\_receipt} \longrightarrow \text{pool\_commitment} \longrightarrow \text{beacon\_verification\_receipt} \xrightarrow{\text{drand BLS}} \text{selection\_record} \longrightarrow \text{tools/analyze.py} }$$

### 3.4 Selection Custody Quintet & External Anchor Contract

To guarantee that the selected blind problem cohort cannot be chosen, manipulated, backdated, or fabricated post-hoc, the blind arm is governed by five cryptographic artifacts:

1. **`POOL.tsv` (Pre-Randomness Candidate Pool):**
   - Format: UTF-8, LF line endings, header row (if present) excluded for indexing.
   - All passing candidate rows are sorted in ascending lexicographical order by stable source identifier.
   - Canonical data row count defines pool size $N$.

2. **`pool_commitment.json` (Pre-Randomness Commitment):**
   - Emitted and committed **prior** to the scheduled drand beacon round.
   - Schema: `representation-lifting-pool-commitment/v1`
   ```json
   {
     "schema_version": "representation-lifting-pool-commitment/v1",
     "pool_sha256": "<SHA-256 hex of POOL.tsv bytes>",
     "pool_size": 123,
     "published_at_unix": 1790000000
   }
   ```

3. **`pool_anchor_receipt.json` (External Pool Timestamp Anchor Receipt):**
   - External anchor proof demonstrating that `POOL.tsv` and `pool_commitment.json` existed in a public transparency log, RFC 3161 timestamp, or OpenTimestamps proof at or prior to the committed publication timestamp.
   - Schema: `representation-lifting-pool-anchor/v1`
   ```json
   {
     "schema_version": "representation-lifting-pool-anchor/v1",
     "pool_sha256": "<SHA-256 hex of POOL.tsv bytes>",
     "commitment_sha256": "<SHA-256 hex of pool_commitment.json bytes>",
     "anchor_type": "rekor | rfc3161 | opentimestamps | git_push",
     "anchor_proof_id": "<external transparency log ID, entry UUID, or proof hash>",
     "verified_timestamp_unix": 1790000000,
     "verifier": "rekor-cli v1.3.0 | gate_verifier",
     "verification_status": "ANCHOR_VERIFIED"
   }
   ```
   - **Validation Rule:** Must bind both `pool_sha256` and `commitment_sha256`, must have `verification_status: "ANCHOR_VERIFIED"`, and must verify `verified_timestamp_unix <= published_at_unix`.
   - **Fail-Closed Policy:** If blind receipts are evaluated without a valid `pool_anchor_receipt.json`, H2 fails closed as **`NOT_EVALUABLE_POOL_TIMESTAMP`**.

4. **`beacon_verification_receipt.json` (External drand BLS Authenticity Receipt):**
   - External BLS threshold signature verification receipt generated by an official pinned drand client/verifier against the quicknet public key.
   - Network Root-of-Trust: Chain `quicknet`, Hash `52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971`, Scheme `bls-unchained-g1-rfc9380`, Genesis `1692803367`, Period `3s`.
   - Public Key: `83cf0f2896adee7eb8b5f01fcad3912212f144e34608613cc4eca455d6ddc45d72181b68dd29695beec6acdee801ac41`
   - Schema: `representation-lifting-beacon-verification/v1`
   ```json
   {
     "schema_version": "representation-lifting-beacon-verification/v1",
     "quicknet_chain_hash": "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971",
     "public_key_hex": "83cf0f2896adee7eb8b5f01fcad3912212f144e34608613cc4eca455d6ddc45d72181b68dd29695beec6acdee801ac41",
     "scheme_id": "bls-unchained-g1-rfc9380",
     "round": 32399079,
     "signature_hex": "<48-byte drand BLS signature hex: 96 hex characters>",
     "signature_length_bytes": 48,
     "drand_client_version": "drand v1.5.8",
     "binary_sha256": "<pinned SHA-256 of verifier binary>",
     "verification_status": "BLS_VERIFIED"
   }
   ```
   - **Validation Rule:** Must bind identical `round`, `signature_hex`, `quicknet_chain_hash`, `public_key_hex`, `scheme_id`, and have `verification_status: "BLS_VERIFIED"`.
   - **Fail-Closed Policy:** If blind receipts are evaluated without a valid `beacon_verification_receipt.json`, H2 fails closed as **`NOT_EVALUABLE_BEACON_AUTHENTICITY`**.

5. **`selection_record.json` (Post-Beacon Selection Record):**
   - Emitted following publication and verification of the scheduled drand round.
   - Schema: `representation-lifting-selection/v1`
   ```json
   {
     "schema_version": "representation-lifting-selection/v1",
     "quicknet_chain_hash": "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971",
     "round": 32399079,
     "signature_hex": "<drand BLS signature hex: strictly 48 bytes / 96 hex chars>",
     "randomness_hex": "<SHA-256 of signature_bytes>",
     "selected": [
       {"index": 61, "case_id": "case_61"},
       {"index": 88, "case_id": "case_88"},
       {"index": 82, "case_id": "case_82"}
     ]
   }
   ```

### 3.5 Mechanical Custody Replay in `tools/analyze.py` (`validate_selection`)
The analysis engine **does not trust** the recorded selection. It mechanically re-derives the entire selection from first principles:
- Asserts $\operatorname{SHA256}(\text{POOL.tsv bytes}) == \text{committed } \texttt{pool\_sha256}$.
- Asserts $\text{canonical row count} == \text{committed } \texttt{pool\_size} = N$.
- Asserts $\texttt{quicknet\_chain\_hash} \equiv \texttt{"52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"}$.
- Asserts Quicknet BLS signature length is strictly 48 bytes (G1): $\operatorname{len}(\operatorname{bytes.fromhex}(\texttt{signature\_hex})) == 48$.
- Asserts $\operatorname{SHA256}(\texttt{signature\_bytes}) \equiv \texttt{randomness\_hex} = R$ (official drand quicknet rule: $\text{rand} := \operatorname{SHA256}(\text{sig})$).
- Recomputes $r_{\text{scheduled}} = \operatorname{compute\_scheduled\_round}(\texttt{published\_at\_unix})$ and asserts $r_{\text{scheduled}} == \texttt{round}$.
- Recomputes $I = \operatorname{select\_indices}(R, N, \text{count}=3)$ via rejection sampling.
- For each index $i \in I$, looks up the $i$-th row in $\text{POOL.tsv}$ to derive expected $\texttt{case\_id}$.
- Asserts that recomputed indices and case IDs match recorded indices and case IDs identically.
- Asserts zero duplicate indices or case IDs.
- Validates external `pool_anchor_receipt.json` and `beacon_verification_receipt.json`.
- Any structural violation, hash mismatch, corrupted signature, tampered index, or invalid external receipt status raises an immediate **`InputContractError`**.
- If selection custody artifacts are omitted when blind receipts exist, H2 fails closed as **`NOT_EVALUABLE`** (`MISSING_SELECTION_CUSTODY`).
- If external pool anchor receipt is omitted when blind receipts exist, H2 fails closed as **`NOT_EVALUABLE_POOL_TIMESTAMP`**.
- If external beacon verification receipt is omitted when blind receipts exist, H2 fails closed as **`NOT_EVALUABLE_BEACON_AUTHENTICITY`**.

---

## 4. Operational Protocols: Search, Gate, & Execution

### 4.1 Mechanical Representation-Search Protocol (`LIFT-NOT-FOUND`)
For each blind problem:
1. **Search Budget:** Exactly 60 minutes wall-clock time.
2. **Deliverable Requirement:** Executable Lean stub conforming to:
   ```lean
   abbrev LiftDom := ...
   abbrev LiftCod := ...
   def liftT : LiftDom → LiftCod := ...
   def invariant : LiftCod → ... := ...
   theorem preservation_bridge ... : ... ↔ ... := by sorry
   ```
3. **Mechanical Verification, Identity Guard, & Target Linkage:**
   - **Toolchain Compilation:** Zero errors on pinned toolchain (`sorry` permitted strictly in `preservation_bridge`).
   - **Identity Guard Check:** Evaluates definitional identity:
     $$\text{isDefEq}(\text{LiftDom}, \text{LiftCod}) \land \text{isDefEq}(\text{liftT}, @\text{id LiftDom}) \implies \text{REJECT (IDENTITY\_GUARD)}$$
   - **Target Linkage Verification:** Meta-checker peels universal $\Pi$-binders, asserts conclusion definitional equality with target statement, and verifies constant identifier `liftT` appears on the lifted side.
4. **Outcome Assignment:**
   - Compiles cleanly, passes Identity Guard, and passes Target Linkage: Locked as `LIFT-FOUND`.
   - Any failure: Mechanically recorded as **`LIFT-NOT-FOUND`**. Role L is skipped (`SKIPPED_LIFT_NOT_FOUND`). **Resampling is strictly prohibited**—the sample is consumed.

### 4.2 Exact-Target Verification & Symmetric Kernel Replay (`addDecl`)
- Compiled native binary (`.lake/build/bin/verifier`) imports candidate modules as pure data via `Lean.importModules`.
- **Zero Lean syntax elaboration occurs post-candidate import**, rendering candidate-authored `elab_rules` and `macro_rules` completely inert against the verifier.
- **Symmetric Kernel Replay:**
  - Role D: Adds `VerifierTrustCore.d_check : targetType := executor_theorem` via `addDecl`.
  - Role L: Mechanically synthesizes proof $\lambda \vec{x}.\, \text{Iff.mpr}\, (\text{bridge}\,\vec{x})\, (\text{lifted}\,\vec{x})$, verifies type matches target, and adds `VerifierTrustCore.synthesized_target` via `addDecl`.
- **Kernel Axiom Audit:** Axioms must satisfy $A_{\text{observed}} \subseteq \{\texttt{propext}, \texttt{Classical.choice}, \texttt{Quot.sound}\}$.
- **Transitive Candidate-Local Non-Circularity:** $\texttt{preservation\_bridge} \notin \text{Deps}^*(\texttt{lifted\_theorem})$.

### 4.3 Executor Isolation, Fresh Contexts, & Fixed Effort Budgets
1. **Context Isolation:**
   - **Direct Executor ($D$):** Fresh context containing only target theorem statement and admissibility manifest. Zero access to search transcript or stub.
   - **Lifted Executor ($L$):** Fresh context containing target theorem statement, admissibility manifest, and frozen stub.
2. **Uniform Prompting:**
   - Neutral prompt text: *"Write a clear, maintainable Lean proof."* Zero length or tactic minimization instruction.
3. **Fixed Model Roles & Single Source of Truth:**
   - Model bindings are governed strictly by the frozen configuration file `tools/executor_config.json` (`schema_version: representation-lifting-executor-config/v1`).
   - **Primary Fixed Model:** `claude-sonnet-4-6` (Anthropic).
   - **Replication Fixed Model:** `gpt-5.6-sol` (OpenAI). Executed independently as a preregistered replication series without pooling.
   - Any textual or configuration mismatch between preregistration and `tools/executor_config.json` fails the freeze gate closed (verified by `tests/test_analyze.py`).
4. **Binding Effort Budget:**
   - Exactly 3 hours wall-clock time per branch; 600s API request timeout.

### 4.4 Immutable Admissibility Manifests (Method Mode)
Machine-readable `admissibility/<case>.json` deny-lists prohibit pre-packaged terminal library lemmas (`Int.fib_succ_mul_fib_pred_sub_fib_sq`, `Nat.fib_gcd`, `Pell.Solution₁`, `IsPrimitiveRoot.geom_sum_eq_zero`).

### 4.5 Procedural Branch-Output Non-Persistence Isolation
- In paired runs (`run_calibration_family`, `run_blind_case`, `run_control_case`), Role D outputs are retained **strictly in harness process memory**.
- Zero single-role receipts or candidate artifacts are persisted to disk while subsequent roles execute.
- Ephemeral build files are restricted to a dedicated `run_tmp_root` wiped across branch boundaries and upon exit.
- Joint receipts are emitted atomically only after both branches conclude. Standalone role CLI execution is marked `[DEV-ONLY]` and disabled from writing receipts unless `--save-receipt` is explicitly requested.

---

## 5. Metrics & Outcome Evaluation

### 5.1 Primary Categorical Outcome
For every problem evaluated, completion is recorded in the discrete registry:
$$O_{\text{completion}} \in \{\text{BOTH}, \text{L-ONLY}, \text{D-ONLY}, \text{NEITHER}, \text{NOT\_EVALUABLE\_INFRA}\}$$

- **`BOTH`:** Both branches successfully produced a verified proof of the literal target statement within the budget.
- **`L-ONLY`:** The lifted branch completed verification; the direct branch failed verification or timed out.
- **`D-ONLY`:** The direct branch completed verification; the lifted branch failed verification or timed out. (In blind cases, includes `LIFT_NOT_FOUND` where Direct succeeds).
- **`NEITHER`:** Neither branch completed verification. (In blind cases, includes `LIFT_NOT_FOUND` where Direct also fails).
- **`NOT_EVALUABLE_INFRA`:** Assigned if any branch experiences an unrecoverable transport or infrastructure failure. Does not convert into proof failure.

### 5.2 Primary Quantitative Metric: Formalization Footprint
Conditional **strictly** on $O_{\text{completion}} = \text{BOTH}$, the footprint differential is evaluated:
$$\Delta W_{\text{token}} = W_L - W_D$$

Where $W_{\text{token}}$ is the **normalized authored Lean lexical token count** computed via `tools/count_lean_tokens.py`:
- **Inclusions:** All newly authored code required by the branch (for $L$: includes `bridge` + `representation` + `theorem`).
- **Exclusions:** Comments, blank lines, whitespace formatting, and `import` declarations.
- **Rule of Non-Comparison:** If $O_{\text{completion}} \neq \text{BOTH}$, $\Delta W_{\text{token}}$ is **undefined (`None`)** and is never imputed, estimated, or extrapolated.

### 5.3 Secondary Metrics
Recorded alongside $W_{\text{token}}$:
1. Number of newly introduced declarations / lemmas ($N_{\text{lemmas}}$).
2. Number of interactive tactic invocations ($N_{\text{tactics}}$).
3. Number of distinct Mathlib definitions referenced.
4. Total model / solver tokens consumed.
5. Elapsed wall-clock time to verification.

---

## 6. Predeclared Hypotheses & Falsification Criteria

### 6.1 Calibration Arm: Sequential Multi-Theorem Amortization (H1)
For each predeclared family $\{T_1, T_2\}$ executed sequentially in the same context:
- Marginal lifted footprint: $\Delta_L^{(2)} = W_L(T_1 + T_2) - W_L(T_1)$
- Marginal direct footprint: $\Delta_D^{(2)} = W_D(T_1 + T_2) - W_D(T_1)$

**Primary Amortization Hypothesis (H1) Conditions:**
1. **Marginal Dividend:**
   $$2 \times \Delta_L^{(2)} \le \Delta_D^{(2)}$$
2. **Cumulative Amortization:**
   $$W_L(T_1 + T_2) < W_D(T_1 + T_2)$$

**Per-Family Falsification & Evaluation Rules:**
- **`PASS`:** Satisfied if and only if **both** inequalities hold:
  $$2\Delta_L^{(2)} \le \Delta_D^{(2)} \quad \land \quad W_L(T_1 + T_2) < W_D(T_1 + T_2)$$
- **`REJECT`:** Assigned if all required proofs verify, but either inequality fails.
- **`NOT_EVALUABLE`:** Assigned if either branch fails to verify $T_1$ or $T_2$ due to proof failure.
- **`NOT_EVALUABLE_INFRA`:** Assigned if execution was interrupted by transport or infrastructure failure.

**Completeness & Conservative Multi-Family Aggregation Rule:**
- **Calibration Completeness Requirement:** Each evaluated model MUST evaluate all 3 predeclared families: `{fibonacci, pell, roots_of_unity}`. If any family is missing for a model, H1 for that model is assigned **`NOT_EVALUABLE`** (`MISSING_CALIBRATION_FAMILIES`).
- **Primary Model Verdict ($H1_{\text{primary}}$):**
  $$H1_{\text{primary}} = \text{PASS} \iff \text{all 3 calibration families yield PASS}$$
  $$\text{Any family REJECT} \implies H1_{\text{primary}} = \text{REJECT}$$
  $$\text{No REJECT, but at least one NOT\_EVALUABLE} \implies H1_{\text{primary}} = \text{NOT\_EVALUABLE}$$
- **Independent Replication Model:** `gpt-5.6-sol` is evaluated under the exact same rule independently. **The replication model never overrides, pools with, or rescues the primary model.**

### 6.2 Blind Arm: Discovery Feasibility (H2)
Across the 3 drand-selected blind problems:
- Evaluates the rate of `LIFT-FOUND` vs. `LIFT-NOT-FOUND`.
- Records $O_{\text{completion}} \in \{\text{BOTH}, \text{L-ONLY}, \text{D-ONLY}, \text{NEITHER}\}$ across all 3 cases.
- Evaluates $\Delta W = W_L - W_D$ **strictly for cases where $O_{\text{completion}} = \text{BOTH}$**.
- **Reporting Rule:** Reported as a descriptive case-series. Zero population extrapolation or percentage claims.

### 6.3 Negative Control Arm: Scoring Integrity (H0)
Evaluated according to the pre-frozen Control Outcome Matrix in Section 2.3:
- If `CONTROL_PASS`: Protocol integrity confirmed.
- If `COMPROMISED` or `CONTROL_MISSING`: **VETO ACTIVATED**. Entire experiment is declared **INVALID (FAIL)** due to demonstrated metric bias or missing control verification; all method-level conclusions of H1 and H2 are invalidated.
- If `CONTROL_INCONCLUSIVE`: Raw data preserved, no positive method-level claim asserted.

---

## 7. Deterministic Analysis Custody & Study Verdict Governance (`tools/analyze.py`)

All analytical categorizations, inequality evaluations, multi-family aggregations, selection custody replays, external anchor contract verifications, and negative control veto checks are encoded into `tools/analyze.py`.

```
Execution Receipts (*.json)      ──┐
POOL.tsv                         ──┼
pool_commitment.json             ──┼──► tools/analyze.py ──► Certified Study Report
pool_anchor_receipt.json         ──┤                         ├── study_verdict (PRIMARY ONLY)
beacon_verification_receipt.json ──┤                         └── replication (SECONDARY ONLY)
selection_record.json            ──┘
```

### Definitive Study Verdict Governance
The top-level study report emits an unambiguous verdict:
```json
{
  "schema_version": "representation-lifting-execution-receipt/v1",
  "study_verdict": "PASS | REJECT | NOT_EVALUABLE | INVALIDATED_BY_CONTROL_VETO | INVALIDATED_CONTROL_MISSING",
  "basis": "PRIMARY_MODEL_ONLY",
  "replication": {
    "status": "PASS | REJECT | NOT_EVALUABLE | INVALIDATED_BY_CONTROL_VETO | INVALIDATED_CONTROL_MISSING",
    "verdict": "...",
    "interpretation": "SECONDARY_REPLICATION_ONLY"
  }
}
```

- **Sole Primary Authority:** `study_verdict` is derived **strictly and exclusively** from the Primary Model (`claude-sonnet-4-6`).
- **Replication Firewall:** The replication model (`gpt-5.6-sol`) is explicitly classified as `SECONDARY_REPLICATION_ONLY`. A passing replication outcome **can never rescue, overturn, or mitigate** an invalidated or failing primary model verdict.
- **Admissibility of Claims:** No claim of study success or method validation may be asserted unless `study_verdict == "PASS"`.

---

## 8. Trusted Computing Base (TCB) Table (v0.17)

$$\boxed{\text{Trusted Computing Base (TCB)}}$$

| Component | Status | Role & Verification Invariant |
|---|---|---|
| **Lean 4.34.0 Kernel** | Trusted | Formal kernel type-checking, definitional equality, and proof replay. |
| **`leanchecker`** | Trusted | Standalone external kernel replay binary; verifies candidate `.olean` files directly through the Lean kernel. |
| **Mathlib / Imported Proof Base** | Trusted | Pinned commit `5ed2965256430c3649e86755f9576b54eca72435` imported proof base. |
| **Compiled Verifier Binary (`verifier`)** | Trusted | Native compiled binary executable (`.lake/build/bin/verifier`). Built once before candidate compilation; hash committed to manifest. Loads modules as pure data via `Lean.importModules` and executes Lean 4 `MetaM` APIs natively. **Zero Lean syntax elaboration occurs post-candidate import.** Emits structured JSON receipts and POSIX exit codes (0 for PASS, 1 for FAIL). |
| **Symmetric Kernel Replay (`addDecl`)** | Trusted | Both Direct (Role D: `VerifierTrustCore.d_check`) and Lifted (Role L: `VerifierTrustCore.synthesized_target`) declare target theorems into the environment via `addDecl` and audit kernel axioms, eliminating any trust asymmetry between branches. |
| **Deterministic Analysis Custody (`analyze.py`)** | Trusted | Frozen analysis adjudicator (`tools/analyze.py`). Mechanically computes $O_{\text{completion}}$, conditional $\Delta W$, dual H1 inequalities, conservative aggregation, selection custody replay, and negative control veto checks from raw JSON receipts. Scope is explicitly conditional on externally verified receipts. |
| **Selection Custody Replay (`validate_selection`)** | Cryptographic Custody | Mechanically reproduces $\text{POOL bytes} \to \text{hash} \to \text{round} \to \text{signature} \to R \to \text{indices} \to \text{cases}$. Asserts Quicknet G1 signature length $\equiv 48$ bytes. |
| **External Pool Timestamp Anchor (`pool_anchor_receipt.json`)** | External Trust Anchor | Public append-only transparency log (Rekor / RFC 3161 / OpenTimestamps) proving that `POOL.tsv` and `pool_commitment.json` existed at or before `published_at_unix`. Missing or unverified fails closed as `NOT_EVALUABLE_POOL_TIMESTAMP`. |
| **External Beacon BLS Verifier (`beacon_verification_receipt.json`)** | External Trust Anchor | Official drand client verifying Quicknet BLS threshold signature against pinned public key `83cf0f28…`. Missing or unverified fails closed as `NOT_EVALUABLE_BEACON_AUTHENTICITY`. |
| **Configuration Root-of-Trust (`executor_config.json`)** | Pinned Constant | Locks model IDs (`claude-sonnet-4-6`, `gpt-5.6-sol`), effort budgets (3h / 30 turns), request timeouts (600s), and transport policies. |
| **Target & Frozen Spec Generators** | Trusted | Harness scripts generating frozen target statement modules and frozen specification modules. |
| **Process Hardening & Mutation Detection** | Hardened Boundary | Environment secret scrubbing (`OPENAI_API_KEY`, etc.), subprocess limits, and pre/post compilation cryptographic SHA-256 workspace snapshot verification. |
| **Procedural Branch-Output Non-Persistence** | Isolation Guarantee | In paired runs (`run_calibration_family`, `run_blind_case`, `run_control_case`), D branch proof code and single-branch receipts exist strictly in harness memory during evaluation and are never persisted to disk until S/L complete. |
| **Official Drand Root-of-Trust** | Pinned Constant | Quicknet chain hash `52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971`, genesis 1692803367, period 3s, public key `83cf0f2896adee7eb8b5f01fcad3912212f144e34608613cc4eca455d6ddc45d72181b68dd29695beec6acdee801ac41`. |
| **AI Models (Roles S, D, L)** | Untrusted | LLM agents generating theorem statements, bridge specifications, and proof terms. |
| **Candidate Source Code** | Untrusted | Raw Lean code written by candidate models. |
| **Candidate Macros, Elaborators, Syntaxes** | Untrusted | Processed only during candidate module compilation in its own process; **completely inert** to the compiled verifier binary. |
| **Candidate `.olean` Files** | Untrusted until certified | Subject to mandatory `leanchecker` kernel replay + semantic `verifier` execution. |
| **Verification Receipt** | Certified Artifact | Machine-readable structured JSON receipt (`schema_version: representation-lifting-execution-receipt/v1`) detailing sub-checks and process exit code 0. |

---

## 9. Execution Checklist & Pre-Freeze Gates

- [x] **Gate 0:** Repository initialized with checked-in Lake project, standalone compiled adjudicator (`.lake/build/bin/verifier`), symmetric kernel replay (`addDecl`), branch non-persistence isolation, frozen experimental drivers (`run_calibration_family`, `run_blind_case`, `run_control_case`), deterministic analysis adjudicator (`tools/analyze.py`), full selection custody replay (`validate_selection`), and External Anchor Contract schemas (`pool_anchor_receipt.json`, `beacon_verification_receipt.json`).
- [ ] **Gate 1:** Mechanical nontriviality script executed on ProofNet-Verified (367 base items).
- [ ] **Gate 2:** Verbatim Lean 4 v4.34.0 compilation filter executed; `EXCLUDED_TOOLCHAIN_INCOMPATIBLE.tsv` generated.
- [ ] **Gate 3:** `POOL.tsv` compiled, sorted, canonical SHA-256 published; `pool_commitment.json` and external timestamp proof recorded in `pool_anchor_receipt.json`.
- [ ] **Gate 4:** Target drand round committed via `tools/drand_schedule.py`, retrieved, and verified via `beacon_verification_receipt.json`.
- [ ] **Gate 5:** Live API Smoke Test executed (`tools/smoke_test_executor.py`).
- [ ] **Gate 6:** Human Ratification by Ivan Nestorov prior to the scheduled publication timestamp of the drand round.

---

## 10. Protocol Amendment History

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
- **Amendment 0.8 $\to$ 0.9:**
  - Independent Module Compilation (`CandidateDModule.lean`, `CandidateSModule.lean`, `CandidateLModule.lean`).
  - Mandatory kernel replay via `leanchecker`.
  - Process & filesystem snapshot guards against unauthorized host mutations.
- **Amendment 0.9 $\to$ 0.10:**
  - Compiled Verifier Adjudicator Executable: Standalone native compiled binary (`.lake/build/bin/verifier`) loading modules via `Lean.importModules`.
  - Immunity to Syntax & Command Hijacking.
  - Structured Verification Receipts & Exit Codes.
  - Explicit TCB Specification.
- **Amendment 0.10 $\to$ 0.11:**
  - D-Branch Kernel `addDecl` Finalization (`VerifierTrustCore.d_check`).
  - Procedural Branch-Output Non-Persistence Isolation for calibration runs.
  - Defense-in-depth static scan hardening.
  - Receipt schema version stabilization.
- **Amendment 0.11 $\to$ 0.12:**
  - Blind Case Experimental Driver (`run_blind_case`) with procedural non-persistence isolation.
  - Preregistered Failure Classification without Resampling (`LIFT_NOT_FOUND`).
  - Rejection-Sampling Specification Alignment.
  - Drand Quicknet Hash Correction (`52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971`).
  - Canary Regression Test Bug Fix.
  - Dedicated Temporary Run Root Isolation (`run_tmp_root`).
  - Release Hygiene & Clean Manifest.
- **Amendment 0.12 $\to$ 0.13:**
  - Restoration of Full Normative Spine ($O_{\text{completion}}$, conditional $\Delta W_{\text{token}}$, dual H1 inequalities, conservative aggregation, independent replication).
  - Negative Control Arm Driver (`run_control_case`) and target `calibration/control_sum_odd.lean`.
  - Deterministic Analysis Custody (`tools/analyze.py`) and analytical unit test suite (`tests/test_analyze.py`).
- **Amendment 0.13 $\to$ 0.14:**
  - Single Source of Truth for Model Configuration (`tools/executor_config.json`, `claude-sonnet-4-6` and `gpt-5.6-sol`).
  - Mandatory Negative Control Veto (`CONTROL_MISSING` / `INVALIDATED_CONTROL_MISSING`).
  - H1 Calibration Arm Completeness (3 mandatory families).
  - Receipt Model ID Enforcement.
- **Amendment 0.14 $\to$ 0.15:**
  - Harness-Analyzer Schema Alignment.
  - Centralized Pre-Analysis Input Contract Validation (`validate_study_inputs`).
  - Blind Selection Record & Set Equality.
  - Per-Model Negative Control Governance.
  - Artifact Hygiene.
- **Amendment 0.15 $\to$ 0.16:**
  - Full Selection Custody Replay Chain (`validate_selection`): Reconstructs $\text{POOL} \to \text{hash} \to \text{round} \to \text{signature} \to R \to \text{indices} \to \text{cases}$.
  - Adversarial Custody Rejection & Missing Selection Fails Closed (`MISSING_SELECTION_CUSTODY`).
  - Definitive Study Verdict Governance (`study_verdict` strictly `PRIMARY_MODEL_ONLY`, replication `SECONDARY_REPLICATION_ONLY`).
- **Amendment 0.16 $\to$ 0.17 (Current / External Anchor Contract Freeze Candidate):**
  - **Explicit External Trust Boundary Declaration:** Preregistration formally declares the exact scope boundary: `analyze.py` deterministically reproduces the selection conditional on externally verified pool-timestamp and drand-BLS authenticity receipts; it does not itself establish those external facts.
  - **External Pool Timestamp Anchor Contract (`pool_anchor_receipt.json`):** Pool commitment author cannot self-report authoritative publication time. Pool commitment must be anchored in an external append-only log or timestamp proof (`representation-lifting-pool-anchor/v1`). If omitted when evaluating blind receipts, H2 fails closed as `NOT_EVALUABLE_POOL_TIMESTAMP`.
  - **External drand BLS Authenticity Contract (`beacon_verification_receipt.json`):** Instead of relying only on internal algebraic consistency ($\operatorname{SHA256}(\text{sig}) = \text{rand}$), external BLS threshold signature authenticity against drand quicknet's public key (`83cf0f28…`) is anchored via an official drand-client verification receipt (`representation-lifting-beacon-verification/v1`). If omitted when evaluating blind receipts, H2 fails closed as `NOT_EVALUABLE_BEACON_AUTHENTICITY`.
  - **Quicknet Signature Length Sanity Check:** Quicknet signatures are in G1 and strictly 48 bytes (96 hex characters). Both `validate_selection` and the external beacon schema enforce $\operatorname{len}(\operatorname{bytes.fromhex}(\texttt{signature\_hex})) == 48$, rejecting fabricated or mismatched curve lengths (such as 96 bytes).
  - **Frozen Contract Formats:** Neither real pool timestamping nor future beacon fetching is performed pre-freeze; v0.17 freezes the exact receipt schemas, verification algorithms, and fail-closed criteria for those future proofs.
