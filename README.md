# representation-lifting-s1

**Scientific Investigation Track:** Formal Representation Lifting & Structural Boundary Audit  
**Author / Principal Investigator:** Ivan Nestorov  
**Repository:** [https://github.com/VolMax-Studio/representation-lifting-s1](https://github.com/VolMax-Studio/representation-lifting-s1)  
**Toolchain Target:** Lean 4 (v4.34.0) / Mathlib v4.34.0 (commit `5ed2965256430c3649e86755f9576b54eca72435`)  
**Preregistration Specification:** [PREREGISTRATION_v0.20_CANDIDATE.md](file:///home/volmax-studio/volmax-projects/iot2/PORTFOLIO/representation-lifting-s1/PREREGISTRATION_v0.20_CANDIDATE.md)  
**Status:** `ARCHITECTURE + ANALYSIS + SELECTION CUSTODY + ROOT-OF-TRUST + GATE-1 INPUT CONTRACT FROZEN / READY FOR PRE-RANDOMNESS GATES`

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
   This automatically downloads and decompresses precompiled `.olean` files directly from `https://cache.mathlib.org/mathlib4`.
4. **Build Compiled Adjudicator Binary:**
   ```bash
   lake build verifier
   ```

---

## Running Test Suites

All regression test suites run deterministically without external API dependencies:

```bash
python3 tests/test_check_bridge.py      # Verifies 12 bridge fixture branches and Identity Guard
python3 tests/test_verify_proof.py      # Verifies direct proof verification, binder matching, and elab/macro hijack rejection
python3 tests/test_verify_lifted.py     # Verifies structural lift, non-circularity, and elab/macro hijack rejection
python3 tests/test_executor_harness.py  # Verifies state machine loops, truncation handling, H1 calibration, blind orchestration, and control execution
python3 tests/test_drand_schedule.py    # Verifies drand quicknet future-round invariants across 1000 grid points and pinned chain hash
python3 tests/test_analyze.py           # Verifies deterministic analysis custody, completion categories, dual H1 inequalities, control veto, and aggregation
python3 tests/test_nontriviality_filter.py # Verifies Gate 1 input contract, anchored extraction, and tri-state filter
python3 tests/test_build_pool.py        # Verifies deterministic pool builder, partition invariant, and real Lean integration
```

---

## Architecture & Governance (v0.14)

1. **Compiled Native Adjudicator Binary (`.lake/build/bin/verifier`):**
   - The verifier is compiled once before candidate evaluation and invoked directly via its native binary.
   - Candidate `.olean` files are loaded as pure data via `Lean.importModules`.
   - **Zero Lean syntax elaboration occurs after candidate import**, rendering candidate-authored `elab_rules`, `macro_rules`, and syntax extensions completely inert against the verifier.
   - Outputs machine-readable JSON verification receipts (`schema_version: representation-lifting-execution-receipt/v1`) and returns POSIX exit codes (0 for PASS, 1 for FAIL).
2. **Symmetric Kernel Declaration Replay (`addDecl`):**
   - Both Direct (Role D: `VerifierTrustCore.d_check`) and Lifted (Role L: `VerifierTrustCore.synthesized_target`) declare their final target theorems into the environment via `addDecl` and audit kernel axioms, eliminating any trust asymmetry between branches.
3. **Deterministic Analysis Custody (`tools/analyze.py`):**
   - Acts as the sole, frozen normative analysis adjudicator mapping execution receipts into scientific verdicts.
   - Computes discrete completion outcomes: $O_{\text{completion}} \in \{\text{BOTH}, \text{L-ONLY}, \text{D-ONLY}, \text{NEITHER}, \text{NOT\_EVALUABLE\_INFRA}\}$.
   - Evaluates footprint differential $\Delta W_{\text{token}} = W_L - W_D$ **strictly conditional on $O_{\text{completion}} = \text{BOTH}$**.
   - Mechanically evaluates dual H1 inequalities ($2\Delta_L^{(2)} \le \Delta_D^{(2)} \land W_L < W_D$) and executes conservative multi-family aggregation.
4. **Procedural Branch-Output Non-Persistence Isolation:**
   - In all paired experimental runs (`run_calibration_family`, `run_blind_case`, `run_control_case`), D branch proof code and single-branch receipts exist **strictly in harness process memory** during evaluation and are never persisted to disk until S/L complete.
   - All ephemeral files (prefixes, stub headers, staging Lean files) are confined to an isolated, per-run `run_tmp_root` that is verified and wiped clean across branch boundaries and upon exit.
   - Prevents candidate Lean code from reading D results at compile-time via IO or file access.
   - Joint paired receipts are emitted atomically only after both branches conclude.
5. **Blind Case Orchestration & Fail-Closed Governance (`run_blind_case`):**
   - Orchestrates the blind evaluation sequence: $D \to S \to L$.
   - The D result is kept strictly in memory; S receives only the problem statement; L receives only the S stub and the problem statement.
   - If S fails (syntax error, kernel rejection, circularity), the run terminates immediately with `LIFT_NOT_FOUND` or `INFRA_FAILURE`. **Resampling is strictly prohibited**—the sample is consumed.
   - Standalone CLI role execution (`tools/executor_harness.py role ...`) is explicitly designated `[DEV-ONLY]` and defaults to not writing receipts to disk unless `--save-receipt` is explicitly requested.
6. **Negative Control Arm & Binding Veto (`run_control_case`):**
   - Evaluates the flat theorem $\sum_{k=0}^{n-1} (2k+1) = n^2$ (`calibration/control_sum_odd.lean`) against pre-frozen gnomon stub (`calibration/ControlGnomonStub.lean`).
   - If the observed outcome is `COMPROMISED` (i.e. $L$-ONLY or $W_L \le W_D$ on the flat target), the automated analysis pipeline activates a binding veto, invalidating all methodological conclusions of H1 and H2.
7. **Exact Preregistered Sampling Formula & Official drand Root of Trust:**
   - Preregistration Section 2.2 explicitly formalizes the rejection sampling algorithm implemented in `tools/select_indices.py`:
     $$H_j = \text{SHA256}(\text{"representation-lifting-s1/v0.1\textbackslash0"} \parallel R \parallel \text{uint64be}(j))$$
     $$L = 2^{256} - (2^{256} \bmod N), \quad v_j < L \implies i = v_j \bmod N$$
   - Pinned official drand quicknet chain hash: `52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971` (period: 3s, genesis: 1692803367).
8. **Independent Module Isolation & Mandatory Kernel Replay:**
   - Candidate code is compiled into independent modules (`CandidateDModule.lean`, `CandidateSModule.lean`, `CandidateLModule.lean`).
   - Every candidate `.olean` is independently validated through the Lean 4 kernel with `leanchecker` prior to semantic checks.
9. **Process Hardening & Filesystem Mutation Detection:**
   - Subprocesses are stripped of sensitive API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GITHUB_TOKEN`, `SSH_AUTH_SOCK`).
   - SHA-256 workspace snapshot guards verify that no host files outside the temporary build directory are created, modified, or deleted during candidate compilation.
10. **Method Mode Machine-Readable Deny-Lists (`admissibility/*.json`):**
    - Primary experimental regime. Models cannot query pre-packaged terminal lemmas (`Int.fib_succ_mul_fib_pred_sub_fib_sq`, `Nat.fib_gcd`, `Pell.Solution₁`, `IsPrimitiveRoot.geom_sum_eq_zero`).
    - Recursively inspects direct constant references in all declarations authored in candidate module.
11. **Structural Lift Architecture & Mechanical Target Synthesis (Role L):**
    - Role S defines representation types (`LiftDom`, `LiftCod`), map (`liftT`), and specification (`BridgeProp : Prop`, `LiftedClaim : Prop`).
    - Role L authors only `preservation_bridge : BridgeProp` and `lifted_theorem : LiftedClaim`.
    - Target theorem is mechanically synthesized and kernel-audited by the verifier:
      `fun xs => (preservation_bridge xs).mpr (lifted_theorem xs)`.
    - Non-circularity is strictly audited: `preservation_bridge ∉ Deps*(lifted_theorem)`.
12. **Sequential Multi-Theorem Calibration State Machine (H1):**
    - `run_calibration_family` executes sequential $T_1 \to T_2$ runs in the same source context for both branches.
    - Evaluates dual conditions: marginal dividend ($2\Delta_L^{(2)} \le \Delta_D^{(2)}$) and cumulative amortization ($W_L(T_1+T_2) < W_D(T_1+T_2)$).
13. **Fixed Model Roles & Budget Normalization:**
    - Primary Model: `claude-sonnet-4-6` (as pinned in `tools/executor_config.json`).
    - Replication Model: `gpt-5.6-sol` (as pinned in `tools/executor_config.json`), evaluated independently without pooling.
    - Request timeout: 600s in `tools/executor_config.json` (eliminating length bias against Role L).
    - Responses cut off by token limit are normalized to `OUTPUT_TRUNCATED`.
14. **Deterministic Selection Custody Replay (`validate_selection`):**
    - The analyzer mechanically reproduces $\text{POOL} \to \text{hash} \to \text{round} \to \text{signature} \to R \to \text{indices} \to \text{cases}$.
    - Enforces Quicknet G1 signature length sanity check ($\operatorname{len}(\operatorname{sig}) == 48$ bytes / 96 hex characters).
    - Fails closed as `NOT_EVALUABLE` (`MISSING_SELECTION_CUSTODY`) if selection custody artifacts are omitted.
15. **External Anchor Contract (`pool_anchor_receipt.json`, `beacon_verification_receipt.json`):**
    - `analyze.py` scope is explicitly bounded: it deterministically reproduces the selection conditional on externally verified receipts, but does not self-attest external facts.
    - `pool_anchor_receipt.json` anchors pool existence prior to beacon round via public append-only transparency log (Rekor / RFC 3161 / OpenTimestamps). Missing receipt $\implies$ `NOT_EVALUABLE_POOL_TIMESTAMP`.
    - `beacon_verification_receipt.json` anchors BLS threshold signature authenticity against quicknet's public key (`83cf0f28…`) via official drand-client verification. Missing receipt $\implies$ `NOT_EVALUABLE_BEACON_AUTHENTICITY`.
16. **Archived drand External Root-of-Trust & Multi-Relay Provenance (v0.19):**
    - `external_roots/drand_quicknet_info_api.raw.json` is a byte-for-byte `curl` download from `api.drand.sh`, raw SHA-256 `3e690bc5…6b194`.
    - `external_roots/drand_quicknet_info_relay2.raw.json` is the same from `api2.drand.sh` (raw SHA-256 identical).
    - `external_roots/drand_quicknet_info_cloudflare.raw.json` is from `drand.cloudflare.com` (trailing newline, raw SHA differs, canonical JSON identical).
    - Each `.raw.json` has a companion `.meta.json` recording URL, UTC fetch time, HTTP status, raw SHA-256, and cross-relay canonical match status.
    - Tests verify all 6 fields (`public_key`, `period`, `genesis_time`, `hash`, `groupHash`, `schemeID`) against the archived raw file, and cross-check canonical equality across all three relays.
    - `QUICKNET_GROUP_HASH` is pinned as a constant in `tools/drand_schedule.py` and exported through `tools/analyze.py`.
    - `tools/analyze.py` strictly validates `public_key_hex` and its 96-byte length against the pinned constant.
    - Packaging enforces mechanical set equality $\operatorname{set}(\text{manifest}) \equiv \operatorname{set}(\text{packaged}) \setminus \{\text{MANIFEST.sha256}\}$, guaranteeing 100% cryptographic coverage of all repository payload files with zero `sha256sum -c` failures.
17. **Gate-1 Input Contract, Unified Adjudicator & Hardened Pool Builder (v0.20 Amendment):**
    - Preserves ratified `representation-lifting-s1-freeze-v0.19` baseline tag as historically immutable.
    - Implemented `tools/extract_proofnet_statement.py`: anchored, fail-closed extraction that strips only trailing proof placeholders (`:= by sorry` / `:= sorry`), eliminates syntax collisions, and hoists imports to the file head. CLI validation mode verifies all 367 entries and their SHA-256 in one pass.
    - Unified Gate 1 / Gate 2 into a single authoritative module `tools/nontriviality_filter.py`, eliminating split-brain between the filter script and pool builder. `tools/nontriviality_filter.sh` converted to a thin CLI wrapper.
    - Upgraded filter contract to a tri-state adjudicator ($0 = \text{NONTRIVIAL}$, $1 = \text{TRIVIAL}$, $2 = \text{INPUT\_ERROR / BASELINE\_INVALID}$) with mandatory fail-closed baseline elaboration check using `sorry`.
    - Eliminates false-negative parse-failure vulnerability, ensuring syntax errors fail closed as input errors rather than passing as nontrivial.
    - Reconciled Gate-2 specification from "verbatim compilation" to exact "canonical statement elaboration under Lean 4.34.0", enumerating the 5 mechanical transformations: extract statement, strip trailing placeholder, hoist imports, prepend `import Mathlib` if absent, and append `:= by sorry` under `maxHeartbeats 200000`.
    - Authoritative ProofNet commit pinned: `160414332dc196583f6c37c310b420d2a3b07c58` (repo `https://github.com/marcusm117/ProofNet-Verified.git`, `data/proofnet-verified.jsonl` SHA-256 `381f4a06548a4ff6d9b923633c94a97b9c70f41033e13023aae31e1161b7f142`).
    - Unambiguous `case_id` format locked: `proofnet-{index:03d}` (from `proofnet-001` through `proofnet-367`), resolving source name collision on `Rudin_exercise_4_8a` (present at indices 168 and 351). `tools/analyze.py::parse_pool_tsv()` enforces global fail-closed rejection of duplicate `case_id`s.
    - Verified by `tests/test_nontriviality_filter.py` with 16 comprehensive tests, including a **non-skippable** 367/367 entry kill-test asserting exact canonical JSONL SHA-256, unique case IDs, and zero leaked `sorry`. Missing dataset triggers an immediate hard test failure.
    - Implemented frozen pre-randomness pool orchestrator `tools/build_pool.py` and regression test suite `tests/test_build_pool.py`. Enforces deterministic `maxHeartbeats 200000`, 600s watchdog timeout, fail-closed suppression of `POOL.tsv` if $N_{\text{INFRA\_HANG}} > 0$, machine-asserted partition invariant $367 = N_{\text{POOL}} + N_{\text{TRIVIAL}} + N_{\text{TOOLCHAIN}} + N_{\text{INPUT}}$, and cryptographic bundle commitment `pool_bundle_manifest.json` with 100% byte-identical reproducibility across runs.
    - External public timestamp anchor rules formalized: the anchor must record the SHA-256 of the **entire `pool_bundle_manifest.json` file**, cryptographically binding source metadata, builder code, and all output file hashes.
    - Added unmocked real Lean integration test in `tests/test_build_pool.py` verifying real `lake env lean` execution on CI runner across major categories (`rfl`, `ring`, non-trivial, broken syntax).
    - `MANIFEST.sha256` updated to cover all 113 payload files with 0 failures on `sha256sum -c`.



