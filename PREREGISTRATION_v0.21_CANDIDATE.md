# representation-lifting-s1: PREREGISTRATION v0.21 CANDIDATE
**Status:** PRE-RANDOMNESS CUSTODY AMENDMENT CANDIDATE — NOT FROZEN (SUPERSEDES v0.20 `4ca9c0c1…`, v0.19 `d5625988…`, v0.18 `3cbe8d58…`, v0.17 `967e266e…`, v0.16 `b3d37f9e…`, v0.15 `2aa3d9d1…`, v0.14 `114a563f…`, v0.13 `84f36cb3…`, v0.12 `364dec3a…`, v0.11 `66558238…`, v0.10 `cd49146a…`, v0.9 `ee8c2dab…`, v0.8 `6701f8f2…`, v0.7 `4f12eae5…`, v0.6 `ecb31e42…`, v0.5 `64e6cde8…`, v0.4 `bdc5c76e…`, v0.3 `da532b0e…`, v0.2 `4fdc0bf4…`, AND v0.1 `254e06d8…`)  
**Ratified Baseline Tag:** `representation-lifting-s1-freeze-v0.20` (commit `f3c8978b55985c0fc76a71ab3d57ba90917204e1`)  
**Carried-Forward Candidate Pool:** run2, `pool_bundle_manifest.json` SHA-256 `aef332f69fb7bf70c0032dc05a383f8fea0085fecbd2ba22281c48ef4c36f7f6`, `POOL.tsv` SHA-256 `398ddcb3d9e915edce681c0d59138950177d7eb096200795f927741fb9743212`, $N = 362$  
**Author / Principal Investigator:** Ivan Nestorov  
**Target Toolchain:** Lean 4 (v4.34.0) / Mathlib v4.34.0 (commit `5ed2965256430c3649e86755f9576b54eca72435`)  
**Repository Location:** `PORTFOLIO/representation-lifting-s1/`  
**GitHub Tracking Repo:** `https://github.com/VolMax-Studio/representation-lifting-s1`  
**Date:** 2026-09-29  

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
│ • Roots of Unity (Geom sum + Re)│        │ • Canonical elaboration on 4.34 │        │ • Symmetric outcome matrix      │
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
  - Canonical Repository: `https://github.com/marcusm117/ProofNet-Verified.git`
  - Authoritative Commit Pin: `160414332dc196583f6c37c310b420d2a3b07c58` (HEAD; byte-for-byte identical to tag `v4.28.0` commit `2171d05b6929db38dedc545f150bd52284e48fd8` on `data/proofnet-verified.jsonl`)
  - Canonical JSONL File: `data/proofnet-verified.jsonl`
  - Canonical JSONL SHA-256: `381f4a06548a4ff6d9b923633c94a97b9c70f41033e13023aae31e1161b7f142` (367 records)
  - Canonical `case_id` Format: `proofnet-{index:03d}` (from `proofnet-001` through `proofnet-367`), derived directly from the unique 1-based JSONL `index` field. Resolves duplicate source name collision (`Rudin_exercise_4_8a` present at index 168 and index 351).
- **Mechanical Exclusion Criteria & Canonical Transformations:**
  1. `tools/extract_proofnet_statement.py`: Anchored, fail-closed extraction from ProofNet-Verified JSONL, stripping trailing proof placeholders (`:=\s*(?:by\s*)?sorry\s*$`).
  2. `tools/nontriviality_filter.py` (authoritative Python module and wrapper `tools/nontriviality_filter.sh`): Tri-state fail-closed test against 4 basic tactics under deterministic `maxHeartbeats 200000` (`rfl`, `decide`, `linarith`, `ring`). Mandatory baseline elaboration check with `sorry` enforces fail-closed rejection of syntax/parse errors ($2 = \text{INPUT\_ERROR / BASELINE\_INVALID}$). Excludes tactic trivialities ($1 = \text{TRIVIAL}$).
  3. Pinned Toolchain Compatibility — Canonical Statement Elaboration under Lean 4 v4.34.0:
     Rather than compiling verbatim unnormalized JSONL snippets, each candidate undergoes exact, mechanical canonical elaboration:
     a. Extract canonical statement from JSONL record (`formal_stmt`, `header`, `helper`).
     b. Remove trailing proof placeholder (`:= by sorry` or `:= sorry`).
     c. Hoist all `import` declarations to the file header.
     d. Prepend `import Mathlib` if absent.
     e. Append `:= by sorry` (for Gate-2 baseline elaboration) or `:= by <tactic>` (for Gate-1 tactic probes) under `set_option maxHeartbeats 200000`.
     Any candidate failing baseline elaboration is assigned to `EXCLUDED_TOOLCHAIN_INCOMPATIBLE.tsv` with compiler error diagnostics.
- **Candidate Pool Frozen Artifact:** `POOL.tsv` (sorted lexicographically by unique `case_id`; column 1 is `case_id`, column 2 is `source_name`). Produced deterministically by `tools/build_pool.py` together with exclusion TSVs, `pool_build_report.json`, and cryptographic bundle commitment `pool_bundle_manifest.json`. `tools/analyze.py::parse_pool_tsv()` enforces global fail-closed rejection of duplicate `case_id`s.
- **Machine-Independent Pool Construction & Fail-Closed Hang Rule:**
  Watchdog timeout is set to 600s strictly to catch hanging processes without truncating normal Mathlib elaboration.
  If any case triggers a watchdog timeout ($N_{\text{INFRA\_HANG}} > 0$), `tools/build_pool.py` strictly fails closed: `POOL.tsv` is NOT emitted, and execution aborts with exit code 2.
  A valid candidate pool exists ONLY when $N_{\text{INFRA\_HANG}} = 0$, guaranteeing that pool composition is 100% deterministic and determined exclusively by Lean 4 heartbeats (`maxHeartbeats 200000`), completely independent of host machine performance. The valid partition equation is:
  $$367 = N_{\text{POOL}} + N_{\text{TRIVIAL}} + N_{\text{TOOLCHAIN\_INCOMPATIBLE}} + N_{\text{INPUT\_ERROR}}$$
- **External Timestamp Anchor Rule (v0.21):**
  The sole external time authority is the public Rekor transparency log (`https://rekor.sigstore.dev`). The anchored object is $M = \operatorname{SHA256}(\text{entire } \texttt{pool\_bundle\_manifest.json})$. Because the manifest binds the SHA-256 of `POOL.tsv`, the builder and filter hashes, and the pinned source corpus, anchoring $M$ irrevocably fixes the pool. The authoritative pool publication time is
  $$T_1 := \texttt{integratedTime}\ \text{of the earliest Rekor entry whose artifact hash is } M \text{ (ties: lowest logIndex)},$$
  regardless of who created that entry. `published_at_unix` is **defined** as $T_1$; it is derived, never chosen. Full contract: §3.5 and §3.8.
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

## 3. External Pool Sampling, drand Selection Custody Protocol, & External Root-of-Trust Contract

### 3.1 Source Corpus & Filtering Pipeline
1. **Base Corpus:** `ProofNet-Verified` commit-pinned repository:
   - **Repository URL:** `https://github.com/marcusm117/ProofNet-Verified.git`
   - **Pinned Commit:** `160414332dc196583f6c37c310b420d2a3b07c58` (HEAD)
   - **Compatible Tag:** `v4.28.0` (`2171d05b6929db38dedc545f150bd52284e48fd8`, byte-for-byte identical JSONL)
   - **Relative Path:** `data/proofnet-verified.jsonl`
   - **Canonical SHA-256:** `381f4a06548a4ff6d9b923633c94a97b9c70f41033e13023aae31e1161b7f142`
   - **Exact Entry Count:** 367 records
2. **Canonical Identification & Collision Resolution:**
   - ProofNet contains 367 entries with 367 unique `index` values (1 to 367), but only 366 unique `name` strings (`Rudin_exercise_4_8a` appears at index 168 and index 351 with distinct statements).
   - Canonical `case_id` is defined as `proofnet-{index:03d}` (from `proofnet-001` through `proofnet-367`).
   - `POOL.tsv` stores `case_id` in column 1 and original `source_name` in column 2.
   - `tools/analyze.py::parse_pool_tsv()` enforces a global fail-closed check rejecting duplicate `case_id`s.
3. **Elimination of Subjective Domain Filter:**  
   Because ProofNet-Verified lacks an authoritative `NumberTheory`/`Algebra` column in its published schema, **no manual domain classification is permitted**. All 367 cases enter the mechanical pipeline. If a topological or analytic problem fails to yield a representation lift, that failure is recorded as an authentic `LIFT-NOT-FOUND`.
4. **Anchored ProofNet Canonical Extraction (`tools/extract_proofnet_statement.py`):**  
   - ProofNet-Verified `formal_stmt` fields end with proof placeholders (`:= by sorry` or `:= sorry`).
   - Direct concatenation with tactic probes would create syntax errors (`... := by sorry := by rfl`), causing false-negative tactic failures where all cases pass as nontrivial.
   - Canonical extraction strictly asserts exactly one `sorry` per record and removes only the anchored trailing proof placeholder `:=\s*(?:by\s*)?sorry\s*$`.
   - All `import` lines from `header`, `helper`, and declaration are hoisted to the head of the file.
   - Fails closed as `INPUT_ERROR` on any syntax ambiguity or extra `sorry`.
   - CLI execution against the JSONL validates all 367 entries and their SHA-256 in one pass.
5. **Tri-State Mechanical Nontriviality Filter (`tools/nontriviality_filter.sh`):**  
   - Enforces strict tri-state fail-closed semantics:
     - `0`: **`NONTRIVIAL`** — Baseline elaboration with `sorry` passes under Lean 4 v4.34.0, and all 4 basic tactics fail to prove the statement.
     - `1`: **`TRIVIAL`** — Proved by at least one of `rfl`, `decide`, `linarith`, `ring` under `set_option maxHeartbeats 200000`. Excluded from pool.
     - `2`: **`INPUT_ERROR / BASELINE_INVALID`** — Fails baseline elaboration with `sorry` (syntax error, undeclared identifier, unstripped sorry, etc.). Halts evaluation for that record with explicit exclusion/error log; never classified as `NONTRIVIAL`.
6. **Deterministic Pool Builder & Gate 1/2 Orchestrator (`tools/build_pool.py`):**  
   - Frozen pre-randomness orchestrator executing mechanical filtration of the 367 source cases.
   - Enforces deterministic resource limits (`set_option maxHeartbeats 200000`) for all Lean compilations.
   - Wall-clock safety watchdog (60s) guards against runaway processes and is strictly categorized as `INFRA_HANG` (never disguised as toolchain incompatibility).
   - Enforces machine-asserted partition invariant over every input record:
     $$367 = N_{\text{POOL}} + N_{\text{TRIVIAL}} + N_{\text{TOOLCHAIN\_INCOMPATIBLE}} + N_{\text{INPUT\_ERROR}} + N_{\text{INFRA\_HANG}}$$
   - Emits byte-reproducible outputs (no wall-clock timestamps in deterministic reports):
     - `POOL.tsv`: Lexicographically sorted list of surviving blind pool theorems (`case_id\tsource_name`).
     - `EXCLUDED_TRIVIAL.tsv`: Proved by `rfl`, `decide`, `linarith`, or `ring`.
     - `EXCLUDED_TOOLCHAIN_INCOMPATIBLE.tsv`: Fails baseline compilation under Lean 4 v4.34.0 or exceeds heartbeat limit.
     - `INPUT_ERROR.tsv`: Violates canonical input contract or duplicate identifiers.
     - `INFRA_HANG.tsv`: Watchdog timeout failure.
     - `pool_build_report.json`: Machine-checked partition accounting.
     - `pool_bundle_manifest.json`: Cryptographic bundle commitment anchoring SHA-256 digests of all output files and builder script.
   - **Pre-Outcome Custody Rule:** `build_pool.py` is written, frozen, and verified strictly on synthetic fixtures prior to ratification; execution on the live 367 ProofNet cases occurs only after public repository freeze.

### 3.2 Pool Exhaustion & Insufficient Pool Rule
The filter pipeline runs strictly deterministically via `tools/build_pool.py`:
$$367 = N_{\text{POOL}} + N_{\text{TRIVIAL}} + N_{\text{TOOLCHAIN\_INCOMPATIBLE}} + N_{\text{INPUT\_ERROR}} + N_{\text{INFRA\_HANG}}$$
If the surviving pool count satisfies $N_{\text{POOL}} < 3$ (or in the extreme $N_{\text{POOL}} = 0$):
- The Blind Transfer Arm immediately terminates with status **`INSUFFICIENT_POOL`**.
- No fallback, loose filtering, domain expansion, statement porting, or alternative benchmarks are permitted.
- The Calibration-Family Arm and Negative Control Arm proceed completely independently.

### 3.3 Scope and Boundary of Automated Analysis (`analyze.py`)

> **Boundary Statement:**  
> `analyze.py` deterministically reproduces the selection conditional on externally verified pool-timestamp and drand-BLS authenticity receipts. It does not itself establish those external facts.

The complete trust chain bridges the boundary between internal deterministic custody and external public trust anchors:

$$\boxed{ \text{POOL.tsv} \xrightarrow{\text{hash}} \text{manifest } M \xrightarrow{\text{earliest Rekor entry}} T_1 \longrightarrow \text{pool\_commitment (derived)} \xrightarrow{T_1 + 600\,\text{s}} \text{drand round} \xrightarrow{\text{BLS}} \text{selection\_record} \longrightarrow \text{tools/analyze.py} }$$

`analyze.py` mechanically verifies the hash bindings, the earliest-entry selection, and $T_1$ equality over the archived raw Rekor API responses. Cryptographic verification of the Rekor Signed Entry Timestamp and inclusion proof is performed externally (`rekor-cli verify`) and recorded in `pool_anchor_receipt.json` (`verifier`); any third party can repeat it from the archived evidence.

### 3.4 Archived External Root-of-Trust (Multi-Relay Provenance, v0.19)

To prevent constant tampering, transcription errors, or internal echo chambers across the codebase, all quicknet parameters are pinned directly to byte-for-byte `curl` downloads from multiple independent drand relays:

| Parameter | Official Value | Verification Invariant |
|---|---|---|
| **Primary Archive** | `external_roots/drand_quicknet_info_api.raw.json` | Byte-for-byte `curl` download from `api.drand.sh` |
| **Cross-Relay Archive** | `external_roots/drand_quicknet_info_relay2.raw.json` | Byte-for-byte from `api2.drand.sh` (raw SHA identical) |
| **Third Relay Archive** | `external_roots/drand_quicknet_info_cloudflare.raw.json` | From `drand.cloudflare.com` (trailing newline, canonical JSON identical) |
| **Provenance Metadata** | `*.meta.json` companion files | URL, UTC fetch time, HTTP status, raw SHA-256, canonical SHA-256, cross-relay match |
| **Primary Raw SHA-256** | `3e690bc527c8a4e78232bc06b5a3cff057c51c68f51b208a1a21b2abd6d6b194` | Verified in unit test suite |
| **drand Chain Hash** | `52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971` | Matches `info["hash"]` |
| **Genesis Timestamp** | `1692803367` (Unix epoch seconds) | Matches `info["genesis_time"]` |
| **Period** | `3` seconds | Matches `info["period"]` |
| **Scheme ID** | `bls-unchained-g1-rfc9380` | Matches `info["schemeID"]` |
| **Group Hash** | `f477d5c89f21a17c863a7f937c6a6d15859414d2be09cd448d4279af331c5d3e` | Matches `info["groupHash"]` — field that caught the v0.18 manual-copy error |
| **Quicknet Public Key** | `83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a` | **96 bytes / 192 hex characters (G2 point)**; matches `info["public_key"]` |

### 3.5 Selection Custody Quintet & External Anchor Contract

The blind arm is governed by five cryptographic artifacts:

1. **`POOL.tsv` (Pre-Randomness Candidate Pool):**
   - Format: UTF-8, LF line endings, header row (if present) excluded for indexing.
   - All passing candidate rows are sorted in ascending lexicographical order by stable source identifier.
   - Canonical data row count defines pool size $N$.

2. **`pool_commitment.json` (Derived Pool Commitment, schema v2):**
   - Generated **mechanically** by `tools/derive_pool_commitment.py` after the manifest anchor exists. It is a derived custody record, not a pre-authored file, and is **not** itself the object of the external timestamp.
   - Schema: `representation-lifting-pool-commitment/v2` (exact key set; no additional keys)
   ```json
   {
     "schema_version": "representation-lifting-pool-commitment/v2",
     "manifest_sha256": "aef332f69fb7bf70c0032dc05a383f8fea0085fecbd2ba22281c48ef4c36f7f6",
     "pool_sha256": "398ddcb3d9e915edce681c0d59138950177d7eb096200795f927741fb9743212",
     "pool_size": 362,
     "published_at_unix": "<integer T1>"
   }
   ```

3. **`pool_anchor_receipt.json` (External Pool Timestamp Anchor Receipt, schema v2) and `rekor_evidence.json`:**
   - `rekor_evidence.json` (schema `representation-lifting-rekor-evidence/v1`, produced by `tools/fetch_rekor_evidence.py`) archives the raw response of `POST /api/v1/index/retrieve {"hash":"sha256:<M>"}` and the raw response of `GET /api/v1/log/entries/{uuid}` for **every** returned UUID.
   - Schema: `representation-lifting-pool-anchor/v2` (exact key set; no additional keys)
   ```json
   {
     "schema_version": "representation-lifting-pool-anchor/v2",
     "anchor_type": "rekor",
     "rekor_url": "https://rekor.sigstore.dev",
     "manifest_sha256": "<M>",
     "pool_sha256": "<SHA-256 of POOL.tsv bytes>",
     "anchor_proof_id": "<UUID of the earliest Rekor entry for M>",
     "anchor_log_index": "<its logIndex>",
     "verified_timestamp_unix": "<its integratedTime = T1>",
     "anchor_evidence_sha256": "<SHA-256 of rekor_evidence.json bytes>",
     "verifier": "<rekor-cli version and verify invocation>",
     "verification_status": "ANCHOR_VERIFIED"
   }
   ```
   - **Validation Rule (v0.21):**
     $$\operatorname{SHA256}(\text{manifest bytes}) = M_{\text{carried-forward}} = \texttt{commitment.manifest\_sha256} = \texttt{anchor.manifest\_sha256}$$
     $$\texttt{manifest.bundle\_files["POOL.tsv"]} = \operatorname{SHA256}(\text{POOL.tsv bytes}) = \texttt{commitment.pool\_sha256} = \texttt{anchor.pool\_sha256}$$
     $$\text{canonical POOL row count} = \texttt{commitment.pool\_size}$$
     $$\texttt{anchor.verified\_timestamp\_unix} = \texttt{commitment.published\_at\_unix} = T_1 \quad (\text{strict equality})$$
     `anchor_proof_id` and `anchor_log_index` must identify the earliest Rekor entry for $M$ in the archived evidence; every archived entry must record artifact hash $M$ (algorithm `sha256`, kind `rekord` or `hashedrekord`) and carry a `signedEntryTimestamp` and `inclusionProof`; the archived entries must equal the index search result exactly; `anchor_evidence_sha256` must equal the SHA-256 of the evidence bytes; the manifest's `builder_sha256` / `filter_sha256` must equal the frozen v0.20 instrument.
   - **Admissible anchor type:** `rekor` only. `git_push` (not externally verifiable), RFC 3161 and OpenTimestamps (not publicly searchable for earlier anchors of the same hash; OpenTimestamps time resolution is coarser than the 600 s safety gap) are inadmissible as the normative anchor. They may be archived as supplementary evidence only.
   - **Retired schemas:** `representation-lifting-pool-commitment/v1` and `representation-lifting-pool-anchor/v1` are rejected with `InputContractError`.
   - **Fail-Closed Policy:** If blind receipts are evaluated without a valid `pool_anchor_receipt.json`, H2 fails closed as **`NOT_EVALUABLE_POOL_TIMESTAMP`**. A receipt supplied without the manifest bytes and the Rekor evidence bytes raises `InputContractError`.

4. **`beacon_verification_receipt.json` (External drand BLS Authenticity Receipt):**
   - External BLS threshold signature verification receipt generated by an official pinned drand client/verifier against the quicknet public key.
   - Schema: `representation-lifting-beacon-verification/v1`
   ```json
   {
     "schema_version": "representation-lifting-beacon-verification/v1",
     "quicknet_chain_hash": "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971",
     "public_key_hex": "83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a",
     "scheme_id": "bls-unchained-g1-rfc9380",
     "round": 32399079,
     "signature_hex": "<48-byte drand BLS signature hex: 96 hex characters>",
     "signature_length_bytes": 48,
     "drand_client_version": "drand v1.5.8",
     "binary_sha256": "<pinned SHA-256 of verifier binary>",
     "verification_status": "BLS_VERIFIED"
   }
   ```
   - **Validation Rule:** Must bind identical `round`, `signature_hex`, `quicknet_chain_hash`, `public_key_hex` (matching official 96-byte G2 key), `scheme_id`, and have `verification_status: "BLS_VERIFIED"`.
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

### 3.6 Mechanical Custody Replay in `tools/analyze.py` (`validate_selection`)
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
- Validates the v0.21 pool custody chain (`tools/pool_custody.validate_pool_custody_v2`: manifest bytes, POOL bytes, commitment/v2, anchor/v2, archived Rekor evidence, earliest-entry rule, $T_1$ equality) **before** deriving the round from `published_at_unix`, and validates `beacon_verification_receipt.json`.
- Asserts Quicknet public key in receipt is strictly 96 bytes (G2, 192 hex chars) and equals `DRAND_QUICKNET_PUBLIC_KEY_HEX`.
- Any structural violation, hash mismatch, corrupted signature, tampered index, or invalid external receipt status raises an immediate **`InputContractError`**.
- If selection custody artifacts are omitted when blind receipts exist, H2 fails closed as **`NOT_EVALUABLE`** (`MISSING_SELECTION_CUSTODY`).
- If external pool anchor receipt is omitted when blind receipts exist, H2 fails closed as **`NOT_EVALUABLE_POOL_TIMESTAMP`**.
- If external beacon verification receipt is omitted when blind receipts exist, H2 fails closed as **`NOT_EVALUABLE_BEACON_AUTHENTICITY`**.

### 3.7 Full Recursive Manifest Coverage Release Invariant
To guarantee that every test fixture, Lean proof, configuration file, and root-of-trust artifact is immutably pinned:
- `MANIFEST.sha256` is generated recursively across the entire repository tree without depth limits.
- To eliminate the self-referential paradox, `MANIFEST.sha256` records checksums for all repository source files while explicitly excluding itself from its own contents.
- An automated packaging check enforces mechanical set equality:
  $$\operatorname{set}(\text{manifest\_paths}) \equiv \operatorname{set}(\text{packaged\_source\_paths}) \setminus \{\text{MANIFEST.sha256}\}$$
- Packaging fails closed if any repository source file is omitted or if any unmanifested file exists in the candidate archive.
- Integrity verification via `sha256sum -c MANIFEST.sha256` must complete with exactly 0 failures.

### 3.8 Carried-Forward Pool, Anti-Grinding Rule & Anchoring Procedure (v0.21)

**Carried-forward pool.** The candidate pool is the output of run2 under the frozen v0.20 instrument (`f3c8978`), $367 = 362 + 1 + 4 + 0$, $N_{\text{INFRA\_HANG}} = 0$. Its identifiers are pinned in `tools/pool_custody.py` (`CARRIED_FORWARD_MANIFEST_SHA256`, `CARRIED_FORWARD_POOL_SHA256`, `CARRIED_FORWARD_POOL_SIZE`). v0.21 has no authority to regenerate, rebuild, or replace the pool; any other manifest is rejected. Run1 (ABORTED / INFRA_HANG, `evidence/pool-build-local-001/`) produced no pool.

**Anti-grinding rule.** The drand round is a deterministic function of $T_1$. If the operator could choose among several anchors of $M$, they could choose among several rounds after observing their randomness. Therefore $T_1$ is the earliest public Rekor entry for $M$, by anyone. Rekor is append-only and searchable by artifact hash, so no earlier anchor can be concealed. Because $M$ is already public (commit `64dd0c6`), a third party may create the first entry; that entry then defines $T_1$ and the study proceeds with it.

**No-abandonment rule.** From the moment any Rekor entry for $M$ exists, the study is committed: the scheduled round is retrieved, the selection is computed and published, and results are reported whatever the selected cases are. Abandoning, re-anchoring, or re-building after an entry exists is a protocol violation and must be reported as such.

**Procedure (all steps after the signed v0.21 freeze tag):**
1. Pre-anchor check: `rekor-cli search --rekor_server https://rekor.sigstore.dev --sha aef332f69fb7bf70c0032dc05a383f8fea0085fecbd2ba22281c48ef4c36f7f6`. The result (expected: none) is recorded. If an entry already exists, skip step 2; the earliest existing entry defines $T_1$.
2. Anchor: sign the manifest bytes (`ssh-keygen -Y sign -n file -f <key> pool_bundle_manifest.json`) and upload (`rekor-cli upload --rekor_server https://rekor.sigstore.dev --artifact pool_bundle_manifest.json --signature pool_bundle_manifest.json.sig --pki-format ssh --public-key <key>.pub`). The signer identity carries no custody weight; only the entry time does.
3. Verify: `rekor-cli verify` with the same arguments (exit 0). Record the exact `rekor-cli` version and command as `verifier`.
4. Archive: `python3 tools/fetch_rekor_evidence.py --manifest … --out custody/rekor_evidence.json`.
5. Derive: `python3 tools/derive_pool_commitment.py … --out-dir custody/`. It prints $T_1$, the scheduled round $r = \operatorname{compute\_scheduled\_round}(T_1)$ and its publication time.
6. Commit and push `custody/` (manifest copy, `POOL.tsv` copy, signature, evidence, commitment, receipt, `SHA256SUMS`). Pushing before the round publishes is recommended, but carries no custody weight: after step 2 no free parameter remains.

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
pool_bundle_manifest.json        ──┼
rekor_evidence.json              ──┼
pool_commitment.json (v2)        ──┼──► tools/analyze.py ──► Certified Study Report
pool_anchor_receipt.json (v2)    ──┤                         ├── study_verdict (PRIMARY ONLY)
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

## 8. Trusted Computing Base (TCB) Table (v0.18)

$$\boxed{\text{Trusted Computing Base (TCB)}}$$

| Component | Status | Role & Verification Invariant |
|---|---|---|
| **Lean 4.34.0 Kernel** | Trusted | Formal kernel type-checking, definitional equality, and proof replay. |
| **`leanchecker`** | Trusted | Standalone external kernel replay binary; verifies candidate `.olean` files directly through the Lean kernel. |
| **Mathlib / Imported Proof Base** | Trusted | Pinned commit `5ed2965256430c3649e86755f9576b54eca72435` imported proof base. |
| **Compiled Verifier Binary (`verifier`)** | Trusted | Native compiled binary executable (`.lake/build/bin/verifier`). Built once before candidate compilation; hash committed to manifest. Loads modules as pure data via `Lean.importModules` and executes Lean 4 `MetaM` APIs natively. **Zero Lean syntax elaboration occurs post-candidate import.** Emits structured JSON receipts and POSIX exit codes (0 for PASS, 1 for FAIL). |
| **Symmetric Kernel Replay (`addDecl`)** | Trusted | Both Direct (Role D: `VerifierTrustCore.d_check`) and Lifted (Role L: `VerifierTrustCore.synthesized_target`) declare target theorems into the environment via `addDecl` and audit kernel axioms, eliminating any trust asymmetry between branches. |
| **Deterministic Analysis Custody (`analyze.py`)** | Trusted | Frozen analysis adjudicator (`tools/analyze.py`). Mechanically computes $O_{\text{completion}}$, conditional $\Delta W$, dual H1 inequalities, conservative aggregation, selection custody replay, and negative control veto checks from raw JSON receipts. Scope is explicitly conditional on externally verified receipts. |
| **Archived drand External Root-of-Trust (Multi-Relay)** | Pinned Artifact | `external_roots/drand_quicknet_info_api.raw.json` (raw SHA-256 `3e690bc5…6b194`), cross-validated with `api2.drand.sh` and `drand.cloudflare.com`. Each has companion `.meta.json` with provenance. Authoritative source for chain hash, period (3s), genesis (1692803367), scheme ID (`bls-unchained-g1-rfc9380`), group hash (`f477d5c8…5d3e`), and 96-byte G2 public key (`83cf0f28…`). All 6 fields verified by automated regression tests. |
| **Selection Custody Replay (`validate_selection`)** | Cryptographic Custody | Mechanically reproduces $\text{POOL bytes} \to \text{hash} \to \text{round} \to \text{signature} \to R \to \text{indices} \to \text{cases}$. Asserts Quicknet G1 signature length $\equiv 48$ bytes. |
| **External Pool Timestamp Anchor (Rekor, v0.21)** | External Trust Anchor | Earliest public Rekor entry for the whole-manifest SHA-256 $M$ defines $T_1$ = `published_at_unix`. Raw API responses archived in `rekor_evidence.json`; bindings and earliest-entry rule checked by `tools/pool_custody.py`; SET/inclusion proof verified externally by `rekor-cli verify`. Missing receipt fails closed as `NOT_EVALUABLE_POOL_TIMESTAMP`; any binding violation raises `InputContractError`. |
| **External Beacon BLS Verifier (`beacon_verification_receipt.json`)** | External Trust Anchor | Official drand client verifying Quicknet BLS threshold signature against pinned 96-byte G2 public key `83cf0f28…`. Missing, unverified, or public key mismatch fails closed as `NOT_EVALUABLE_BEACON_AUTHENTICITY` or `InputContractError`. |
| **Configuration Root-of-Trust (`executor_config.json`)** | Pinned Constant | Locks model IDs (`claude-sonnet-4-6`, `gpt-5.6-sol`), effort budgets (3h / 30 turns), request timeouts (600s), and transport policies. |
| **Target & Frozen Spec Generators** | Trusted | Harness scripts generating frozen target statement modules and frozen specification modules. |
| **Process Hardening & Mutation Detection** | Hardened Boundary | Environment secret scrubbing (`OPENAI_API_KEY`, etc.), subprocess limits, and pre/post compilation cryptographic SHA-256 workspace snapshot verification. |
| **Procedural Branch-Output Non-Persistence** | Isolation Guarantee | In paired runs (`run_calibration_family`, `run_blind_case`, `run_control_case`), D branch proof code and single-branch receipts exist strictly in harness memory during evaluation and are never persisted to disk until S/L complete. |
| **Official Drand Root-of-Trust** | Pinned Constant | Quicknet chain hash `52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971`, genesis 1692803367, period 3s, G2 public key (96 bytes) `83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a`. |
| **AI Models (Roles S, D, L)** | Untrusted | LLM agents generating theorem statements, bridge specifications, and proof terms. |
| **Candidate Source Code** | Untrusted | Raw Lean code written by candidate models. |
| **Candidate Macros, Elaborators, Syntaxes** | Untrusted | Processed only during candidate module compilation in its own process; **completely inert** to the compiled verifier binary. |
| **Candidate `.olean` Files** | Untrusted until certified | Subject to mandatory `leanchecker` kernel replay + semantic `verifier` execution. |
| **Verification Receipt** | Certified Artifact | Machine-readable structured JSON receipt (`schema_version: representation-lifting-execution-receipt/v1`) detailing sub-checks and process exit code 0. |

---

## 9. Execution Checklist & Pre-Freeze Gates

- [x] **Gate 0:** Repository initialized with checked-in Lake project, standalone compiled adjudicator (`.lake/build/bin/verifier`), symmetric kernel replay (`addDecl`), branch non-persistence isolation, frozen experimental drivers (`run_calibration_family`, `run_blind_case`, `run_control_case`), deterministic analysis adjudicator (`tools/analyze.py`), full selection custody replay (`validate_selection`), External Anchor Contract schemas (`pool_anchor_receipt.json`, `beacon_verification_receipt.json`), and multi-relay archived drand root (`external_roots/drand_quicknet_info_{api,relay2,cloudflare}.raw.json` with companion `.meta.json`).
- [x] **Gate 1:** Mechanical nontriviality evaluation executed on ProofNet-Verified (367 items) — run2, frozen v0.20 builder.
- [x] **Gate 2:** Canonical statement elaboration under Lean 4 v4.34.0 executed; `EXCLUDED_TOOLCHAIN_INCOMPATIBLE.tsv` generated (4 cases) — run2.
- [ ] **Gate 3a (v0.21 freeze precondition):** Rekor dry run on a **dummy artifact** (never the pool manifest): upload, verify, fetch evidence, and commit it as `tests/fixtures/rekor_real_entry_dryrun.json`. `tests/test_pool_custody.py::test_real_rekor_dryrun_entry_parses` must run (not skip) and pass.
- [ ] **Gate 3b:** v0.21 human-ratified signed freeze tag exists; pre-anchor `rekor-cli search` for $M$ recorded.
- [ ] **Gate 3c:** Manifest anchored in Rekor; `rekor-cli verify` exit 0; `rekor_evidence.json`, `pool_commitment.json` (v2), `pool_anchor_receipt.json` (v2) derived mechanically and committed.
- [ ] **Gate 4:** Target drand round $r = \operatorname{compute\_scheduled\_round}(T_1)$ retrieved and verified via `beacon_verification_receipt.json`.
- [ ] **Gate 5:** Live API Smoke Test executed (`tools/smoke_test_executor.py`).
- [ ] **Gate 6:** Human Ratification by Ivan Nestorov (v0.21 freeze tag) prior to the manifest anchor.

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
- **Amendment 0.16 $\to$ 0.17:**
  - Explicit External Trust Boundary Declaration: `analyze.py` scope is conditional on externally verified receipts.
  - External Pool Timestamp Anchor Contract (`pool_anchor_receipt.json`).
  - External drand BLS Authenticity Contract (`beacon_verification_receipt.json`).
  - Quicknet G1 Signature Length Sanity Check: enforces $\operatorname{len}(\operatorname{sig}) == 48$ bytes.
- **Amendment 0.17 $\to$ 0.18:**
  - **Archived Primary Root-of-Trust (`external_roots/drand_quicknet_info.json`):** Downloaded and archived the official `/info` response for quicknet chain (`52db9ba7…`), pinning its canonical SHA-256. Test suite validates all 5 constants against this archived file.
  - **Quicknet Public Key Correction (G2, 96 Bytes):** Replaced truncated 48-byte key with the true official 96-byte (192 hex character) G2 public key `83cf0f28…45a`.
  - **Active Public Key Enforcement in `analyze.py`:** `validate_selection` actively verifies that `beacon_verification["public_key_hex"]` is present, valid hex, exactly 96 bytes, and identical to `DRAND_QUICKNET_PUBLIC_KEY_HEX`. Adversarial tests verify rejection of forged keys or length violations.
  - **Full Recursive Manifest Coverage Invariant:** Eliminated directory depth truncation in manifest generation. Packaging verifies mechanical set equality $\operatorname{set}(\text{manifest}) \equiv \operatorname{set}(\text{packaged})$, ensuring all fixture files are cryptographically anchored.
- **Amendment 0.18 $\to$ 0.19 (Current / Multi-Relay Provenance Fix):**
  - **Root Cause:** v0.18's `external_roots/drand_quicknet_info.json` was hand-transcribed via `cat <<'EOF'`, not fetched. The `groupHash` field was incorrect (`…59413d2be47718da75ec…` vs true `…59414d2be09cd448d4…`). While functionally harmless (analyzer does not use `groupHash`), the file falsely claimed to be a primary source archive.
  - **Multi-Relay Raw Download:** Replaced hand-copied file with byte-for-byte `curl` downloads from three independent relays: `api.drand.sh` (raw SHA `3e690bc5…`), `api2.drand.sh` (identical raw SHA), and `drand.cloudflare.com` (trailing newline, canonical JSON identical).
  - **Provenance Metadata:** Each `.raw.json` has a companion `.meta.json` recording source URL, UTC fetch timestamp, HTTP status, raw SHA-256, Python-canonical JSON SHA-256, and cross-relay match status.
  - **Extended Field Coverage:** Tests now verify all 6 `/info` fields (`public_key`, `period`, `genesis_time`, `hash`, `groupHash`, `schemeID`) against the archived raw file. `groupHash` is specifically included because it was the field that exposed the v0.18 provenance failure.
  - **Cross-Relay Canonical Equality Test:** New `test_cross_relay_canonical_provenance` proves that `json.dumps(sort_keys=True)` output is identical across all three relay archives.
  - **Pinned `QUICKNET_GROUP_HASH` Constant:** Added `QUICKNET_GROUP_HASH = "f477d5c89f21a17c863a7f937c6a6d15859414d2be09cd448d4279af331c5d3e"` to `tools/drand_schedule.py` and exported via `tools/analyze.py` (`DRAND_QUICKNET_GROUP_HASH`). Both `tests/test_analyze.py` and `tests/test_drand_schedule.py` now explicitly assert this pinned constant against the raw root.
  - **Manifest Self-Referential Paradox Resolved:** Excluded `MANIFEST.sha256` from hashing itself, eliminating the dummy hash entry (`e3b0c44…`). The packaging invariant is formalized as $\operatorname{set}(\text{manifest\_paths}) \equiv \operatorname{set}(\text{packaged\_source\_paths}) \setminus \{\text{MANIFEST.sha256}\}$, guaranteeing `sha256sum -c MANIFEST.sha256` passes with 0 failures across all 107 repository payload files.
- **Amendment 0.19 $\to$ 0.20 (Gate-1 Input Contract & ProofNet Pinning Amendment):**
  - **Preservation of Ratified Baseline:** The human-ratified tag `representation-lifting-s1-freeze-v0.19` (commit `f2cae4d`) remains historically intact and cryptographically pinned. This amendment is adopted before pool generation, timestamp anchor, or drand sampling, ensuring **zero outcome leakage**.
  - **Root Cause of Gate-1 Vulnerability:** In v0.19, `tools/nontriviality_filter.sh` appended `:= by $TAC` directly to target snippets. Because ProofNet-Verified theorem statements already terminate with `:= by sorry` or `:= sorry`, direct concatenation produced invalid Lean syntax (`:= by sorry := by rfl`), causing Lean elaboration to fail on all tactics and creating a critical false-negative vulnerability (trivial theorems passing as NONTRIVIAL due to parse failure).
  - **Anchored, Fail-Closed Canonical Extraction (`tools/extract_proofnet_statement.py`):** Implemented mechanical extractor that strictly verifies exactly one `sorry` per record, strips only the anchored trailing proof placeholder `:=\s*(?:by\s*)?sorry\s*$`, hoists all imports to the head of the file, and fails closed (`INPUT_ERROR`) on any formatting anomaly. Validated across all 367 ProofNet-Verified records with zero errors. Full CLI validation mode (`extract_proofnet_statement.py <path>`) verifies SHA-256 and extracts all 367 statements in one pass.
  - **Authoritative ProofNet Corpus Pinning:**
    - Canonical Repository: `https://github.com/marcusm117/ProofNet-Verified.git`
    - Pinned Commit: `160414332dc196583f6c37c310b420d2a3b07c58` (HEAD; byte-for-byte identical to tag `v4.28.0` commit `2171d05b6929db38dedc545f150bd52284e48fd8` on `data/proofnet-verified.jsonl`)
    - Canonical JSONL File: `data/proofnet-verified.jsonl`
    - Canonical JSONL SHA-256: `381f4a06548a4ff6d9b923633c94a97b9c70f41033e13023aae31e1161b7f142` (367 records)
  - **Case ID Collision Resolution (`proofnet-{index:03d}`):** The ProofNet dataset has 367 entries and 367 unique `index` values, but only 366 unique `name` strings (`Rudin_exercise_4_8a` appears twice: at index 168 and index 351, with distinct mathematical statements). To eliminate collision risk before selection, canonical `case_id` is defined as `proofnet-{index:03d}` (from `proofnet-001` through `proofnet-367`), with `source_name` preserved as column 2 in `POOL.tsv`.
  - **Global Fail-Closed Duplicate Check (`tools/analyze.py`):** `parse_pool_tsv()` parses row-by-row and strictly raises `InputContractError` if any duplicate `case_id` is detected.
  - **Unified Authoritative Gate-1 / Gate-2 Module (`tools/nontriviality_filter.py`):**
    - Eliminated split-brain implementation between shell filter and pool builder. `tools/nontriviality_filter.py` provides the single authoritative implementation of `evaluate_statement()` and `default_lean_runner()`, directly imported and executed by `tools/build_pool.py`.
    - `tools/nontriviality_filter.sh` converted to a thin CLI wrapper executing `python3 tools/nontriviality_filter.py "$@"`.
    - Tri-state fail-closed contract: `0 = NONTRIVIAL`, `1 = TRIVIAL`, `2 = INPUT_ERROR / BASELINE_INVALID`.
  - **Canonical Statement Elaboration under Lean 4 v4.34.0 (Gate 2):**
    Reconciled wording from "verbatim compilation" to exact "canonical statement elaboration under Lean 4.34.0", enumerating the 5 mechanical transformations:
    1. Extract canonical statement from JSONL (`formal_stmt`, `header`, `helper`).
    2. Strip anchored trailing proof placeholder (`:= by sorry` or `:= sorry`).
    3. Hoist all `import` declarations to the file header.
    4. Prepend `import Mathlib` if absent.
    5. Append `:= by sorry` (baseline) or `:= by <tactic>` under deterministic `set_option maxHeartbeats 200000`.
  - **Machine-Independent Pool Construction & Fail-Closed Hang Rule (`tools/build_pool.py`):**
    - Watchdog timeout raised to 600s to avoid false hangs during normal Mathlib loading.
    - If any case experiences a watchdog timeout ($N_{\text{INFRA\_HANG}} > 0$), `tools/build_pool.py` strictly fails closed: `POOL.tsv` is NOT emitted, and execution aborts with exit code 2.
    - A valid candidate pool exists ONLY when $N_{\text{INFRA\_HANG}} = 0$, guaranteeing that pool composition is 100% deterministic and determined exclusively by Lean 4 heartbeats (`maxHeartbeats 200000`), completely independent of host machine performance.
    - Valid partition equation: $367 = N_{\text{POOL}} + N_{\text{TRIVIAL}} + N_{\text{TOOLCHAIN\_INCOMPATIBLE}} + N_{\text{INPUT\_ERROR}}$.
  - **Whole-Manifest Cryptographic Timestamp Anchor Rule:**
    The external public timestamp anchor (Rekor, RFC 3161, OpenTimestamps) records the SHA-256 of the **entire `pool_bundle_manifest.json` file**, rather than merely the internal `bundle_sha256` map. This cryptographically binds builder script metadata and hash, source repository and commit metadata, and all output file hashes under the immutable timestamp proof.
  - **Adversarial & Real Lean Integration Test Suites (`tests/test_nontriviality_filter.py`, `tests/test_build_pool.py`):**
    - `test_nontriviality_filter.py`: 16 comprehensive tests including non-skippable 367 kill-test and tactic fail-closed tests.
    - `test_build_pool.py`: Added unmocked integration test executing real `lake env lean` against synthetic cases (`rfl` -> TRIVIAL, `ring` -> TRIVIAL, non-trivial -> POOL, syntax error -> TOOLCHAIN_INCOMPATIBLE), asserting zero hangs and valid partition invariant on CI runner.
  - **Manifest Coverage Expansion:** `MANIFEST.sha256` expands to 113 payload files (+`PREREGISTRATION_v0.20_CANDIDATE.md`, +`tools/extract_proofnet_statement.py`, +`tests/test_nontriviality_filter.py`, +`tools/nontriviality_filter.py`, +`tools/build_pool.py`, +`tests/test_build_pool.py`), strictly preserving set equality $\operatorname{set}(\text{manifest}) \equiv \operatorname{set}(\text{packaged}) \setminus \{\text{MANIFEST.sha256}\}$ with 0 failures on `sha256sum -c`.
  - **Zero Protocol Drift:** No changes made to Lean verification kernel, H1/H2 hypothesis rules, selection custody, drand parameters, executor state machines, models, control matrix, or analysis adjudicator.
- **Amendment 0.20 $\to$ 0.21 (Current / Pre-Randomness Custody Amendment):**
  - **Trigger:** Pre-anchor review after run2 found that the frozen v0.20 preregistration (§3.5: anchor must bind `commitment_sha256`; `verified_timestamp_unix <= published_at_unix`; whole-manifest anchor) and the frozen `tools/analyze.py` (strict `==`; no `commitment_sha256` or manifest check; no generator for `pool_commitment.json`) were mutually unsatisfiable with a truthful external timestamp. Recorded in `evidence/PRE_RANDOMNESS_CUSTODY_BLOCKER_v0.20.md` (commit `64dd0c6`) and its erratum, **before** any anchor, drand round, or selection.
  - **Timestamp semantics:** `published_at_unix` is defined as $T_1$, the integratedTime of the earliest Rekor entry for the whole-manifest SHA-256. Strict equality is retained and is now satisfiable by construction. `pool_commitment.json` is derived after the anchor and is not itself timestamped; `commitment_sha256` is removed from the anchor contract.
  - **Anti-grinding:** earliest-entry rule (§3.8) and no-abandonment rule; normative anchor restricted to Rekor.
  - **Code:** new `tools/pool_custody.py` (v2 schemas, Rekor evidence parser, chain validator, carried-forward pins), `tools/fetch_rekor_evidence.py`, `tools/derive_pool_commitment.py`; `tools/analyze.py::validate_selection` requires manifest and evidence bytes with an anchor and validates the chain before deriving the round; v1 custody schemas retired; `published_at_unix` must be an integer.
  - **Tests:** new `tests/test_pool_custody.py` (valid chain, every binding mutation, timestamp mismatch, inadmissible anchor types, evidence tampering, anti-grinding, v0.20 circular fixture regression, frozen builder/filter byte identity, freeze-gate real Rekor fixture); `tests/test_analyze.py` custody fixture migrated to v2 with analyzer-boundary tests.
  - **Zero Protocol Drift:** No change to the ProofNet corpus or pin, Gate-1/Gate-2 semantics, `tools/build_pool.py`, `tools/nontriviality_filter.py`, the carried-forward 362-case pool, drand parameters, `tools/select_indices.py`, `tools/drand_schedule.py`, H0/H1/H2, scoring, model bindings, executor state machines, or verdict semantics.
