# representation-lifting-s1: PREREGISTRATION v0.10 CANDIDATE
**Status:** READY FOR CLAUDE GATE / HUMAN RATIFICATION (SUPERSEDES v0.1 `254e06d8…`, v0.2 `4fdc0bf4…`, v0.3 `da532b0e…`, v0.4 `bdc5c76e…`, v0.5 `64e6cde8…`, v0.6 `ecb31e42…`, v0.7 `4f12eae5…`, v0.8 `6701f8f2…`, AND v0.9 `ee8c2dab…`)  
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
  1. `tools/nontriviality_filter.sh`: Excludes one-line tactic trivialities (`by rfl`, `by simp`, `by ring`, `by omega`, `by decide`, `by aesop`, `by linarith`).
  2. Pinned Toolchain Compatibility: Verbatim elaboration check under Lean 4 v4.34.0.
- **Candidate Pool Frozen Artifact:** `POOL.tsv` (sorted lexicographically by ProofNet ID; canonical SHA-256 published prior to drand round).
- **Selection Formula:** 
  $$\text{index}_i = (\text{round\_randomness} + i) \pmod{|P|}, \quad i \in \{0, 1, 2\}$$
- **Future Beacon Commitment:** drand quicknet (`https://api.drand.sh/52db9ba70e0cc0f6eaf7803dd07447a1f547773563d1a107027da8b0025813ac`) committed at +2 future round offset.

---

### 2.3 Negative Control Arm (Scoring & Diagnostic Integrity)
Uses the classical theorem $\sum_{i=0}^{n-1} (2i + 1) = n^2$ with a trivial/canonical gnomon representation prefix to evaluate metric symmetry and prevent false claims of dividend.

**Frozen Negative Control Matrix:**
| Condition | Expected Direct ($W_D$) | Expected Lifted ($W_L$) | Diagnostic Implication |
|---|---|---|---|
| Natural inductive proof | Low ($\approx 40$ tokens) | Higher ($\approx 120$ tokens) | Baseline: Setup overhead is real and non-zero on simple targets. |
| Injected Trivial Bridge ($T \equiv \text{id}$) | N/A | **REJECTED** | Falsifies Identity Guard (AND semantics: $\text{LiftDom}=\text{LiftCod} \land \text{liftT}=\text{id}$). |
| Injected Tautological Bridge ($P \leftrightarrow P$) | N/A | **REJECTED** | Falsifies Non-Tautological Bridge filter. |
| Negative Dividend Outcome ($\Delta_L^{(2)} > \Delta_D^{(2)}$) | N/A | **H1 FALSIFIED** | Proves the metric is capable of returning an unadulterated negative result. |

---

## 3. Trusted Computing Base (TCB) & Semantic Custody (v0.10)

### 3.1 Explicit Trusted Computing Base (TCB) Table

$$\boxed{\text{Trusted Computing Base (TCB)}}$$

| Component | Status | Role & Verification Invariant |
|---|---|---|
| **Lean 4.34.0 Kernel** | Trusted | Formal kernel type-checking, definitional equality, and proof replay. |
| **`leanchecker`** | Trusted | Standalone external kernel replay binary; verifies candidate `.olean` files directly through the Lean kernel. |
| **Mathlib / Imported Proof Base** | Trusted | Pinned commit `5ed2965256430c3649e86755f9576b54eca72435` imported proof base. |
| **Compiled Verifier Binary (`verifier`)** | Trusted | Native compiled binary executable (`.lake/build/bin/verifier`). Built once before candidate compilation; hash committed to manifest. Loads modules as data via `Lean.importModules` and executes Lean 4 `MetaM` APIs natively. **Zero Lean syntax elaboration occurs post-candidate import.** Emits structured JSON receipts and POSIX exit codes (0 for PASS, 1 for FAIL). |
| **Target & Frozen Spec Generators** | Trusted | Harness scripts generating frozen target statement modules and frozen specification modules. |
| **Process Hardening & Mutation Detection** | Hardened Boundary | Environment secret scrubbing (`OPENAI_API_KEY`, etc.), subprocess limits, and pre/post compilation cryptographic SHA-256 workspace snapshot verification. |
| **AI Models (Roles S, D, L)** | Untrusted | LLM agents generating theorem statements, bridge specifications, and proof terms. |
| **Candidate Source Code** | Untrusted | Raw Lean code written by candidate models. |
| **Candidate Macros, Elaborators, Syntaxes** | Untrusted | Processed only during candidate module compilation in its own process; **completely inert** to the compiled verifier binary. |
| **Candidate `.olean` Files** | Untrusted until certified | Subject to mandatory `leanchecker` kernel replay + semantic `verifier` execution. |
| **Model Compiler Diagnostics** | Untrusted | Error messages and diagnostics returned to the model during retry loops. |
| **Verification Receipt** | Certified Artifact | Machine-readable structured JSON receipt detailing sub-checks (`verdict`, `checks`, `axioms_used`, `synthesized_axioms`) and process exit code 0. |

---

### 3.2 The Architectural Shift: Compiled Adjudicator vs. Elaborated Script

The primary vulnerability resolved in v0.10 is the **Command Elaborator Hijack** identified in Gate Review v0.9.

In v0.9, the checker was a `.lean` source script that imported candidate modules:
$$\text{Candidate.olean} \xrightarrow{\text{import Candidate}} \boxed{\text{ELABORATE trusted } \texttt{\#eval!}} \longrightarrow \text{verifier}$$

Because Lean modules export syntax extensions, macros, and command elaborators, an adversarial candidate could register:
```lean
elab_rules : command
  | `(#eval! $_) => Lean.logInfo "VERIFY_LIFTED_SENTINEL_OK"
```
When the checker elaborated `#eval! runVerifyLifted ...`, Lean's command dispatcher routed execution to the candidate's custom elaborator, emitting the sentinel string and returning exit code 0 without ever running the verification algorithm. `leanchecker` passed because the kernel environment remained well-formed.

**v0.10 Architectural Solution:**
$$\boxed{\text{Trusted Compiled Binary}} \xrightarrow{\texttt{importModules}(\text{Candidate.olean})} \boxed{\text{Direct MetaM / Environment API}} \longrightarrow \text{Exit Code + JSON Receipt}$$

1. **Zero Lean Syntax Elaboration Post-Import:**
   The verifier executable (`.lake/build/bin/verifier`) is a native C/binary program compiled by Lake *before* candidate evaluation. At runtime, it calls `Lean.importModules` to load module declarations directly into memory as pure data. No Lean code, commands, or `#eval!` statements are ever elaborated after the candidate module is loaded.
2. **Deterministic Process Exit Code:**
   The verdict is determined strictly by the POSIX exit code of the compiled program (0 for PASS, 1 for FAIL), completely eliminating reliance on stdout string sentinels that could be spoofed.
3. **Structured Machine-Readable Receipts:**
   The verifier emits a JSON receipt containing explicit boolean outcomes for every sub-check:
   ```json
   {
     "verdict": "PASS",
     "subcommand": "lifted",
     "candidate_module": "CandidateLModule",
     "spec_module": "FrozenSpecModule",
     "target_declaration": "frozen_target",
     "checks": {
       "modules_found": true,
       "method_mode": true,
       "bridge_type": true,
       "lifted_type": true,
       "non_circular": true,
       "target_synthesis": true,
       "axioms": true
     },
     "synthesized_axioms": ["propext"]
   }
   ```

---

### 3.3 Semantic Verification Regimes

1. **Exact Target Match & Method Mode (Role D):**
   - Candidate compiled into isolated `CandidateDModule.lean`.
   - `leanchecker CandidateDModule` validates kernel integrity.
   - `verifier target CandidateDModule frozen_target executor_theorem [prohibited]` verifies:
     - Definitional equality: $\text{type}(\texttt{executor\_theorem}) \equiv_{\text{def}} \text{type}(\texttt{frozen\_target})$.
     - Kernel axioms $\subseteq \{\texttt{propext}, \texttt{Classical.choice}, \texttt{Quot.sound}\}$.
     - Method Mode Deny-List: Zero direct constant references to prohibited terminal lemmas across all candidate declarations.

2. **Representation Search Verification (Role S):**
   - Candidate compiled into isolated `CandidateSModule.lean`.
   - `leanchecker CandidateSModule` validates kernel integrity.
   - `verifier bridge CandidateSModule frozen_target [prohibited]` verifies:
     - Zero `sorryAx` anywhere in specification.
     - Identity Guard (AND semantics): $\text{isDefEq}(\text{LiftDom}, \text{LiftCod}) \land \text{isDefEq}(\text{liftT}, @\text{id LiftDom}) \implies \text{REJECT}$.
     - Sequential dependent binder type equality with target statement.
     - Non-tautological equivalence conclusion containing `liftT` and matching `LiftedClaim`.

3. **Structural Lift Verification & Mechanical Synthesis (Role L):**
   - Candidate compiled into isolated `CandidateLModule.lean` (importing `FrozenSpecModule`).
   - `leanchecker CandidateLModule` validates kernel integrity.
   - `verifier lifted CandidateLModule FrozenSpecModule frozen_target [prohibited]` verifies:
     - Kernel axioms of `preservation_bridge` and `lifted_theorem` $\subseteq \{\texttt{propext}, \texttt{Classical.choice}, \texttt{Quot.sound}\}$.
     - Type definitional equalities: $\text{type}(\texttt{preservation\_bridge}) \equiv_{\text{def}} \texttt{BridgeProp}$ and $\text{type}(\texttt{lifted\_theorem}) \equiv_{\text{def}} \texttt{LiftedClaim}$.
     - Transitive candidate-local non-circularity: $\texttt{preservation\_bridge} \notin \text{Deps}^*(\texttt{lifted\_theorem})$.
     - **Mechanical Target Synthesis:** Dynamically constructs proof $\lambda \vec{x}.\, \text{Iff.mpr/mp}\, (\texttt{preservation\_bridge}\,\vec{x})\, (\texttt{lifted\_theorem}\,\vec{x})$, verifies type matches `frozen_target`, adds synthesized theorem to environment, and performs kernel axiom audit.

---

### 3.4 Process Hardening & Filesystem Mutation Detection

To preserve semantic custody on Linux host systems without relying on unprivileged user namespace permissions restricted by Ubuntu 24.04 AppArmor profiles:
- **Environment Variable Scrubbing:** Subprocesses executing candidate Lean compilation are stripped of sensitive API keys and authentication tokens (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GITHUB_TOKEN`, `SSH_AUTH_SOCK`).
- **Filesystem Mutation Detection:** A cryptographic SHA-256 snapshot of all repository directories (`tools/`, `fixtures/`, `calibration/`, `admissibility/`) is taken immediately prior to candidate compilation and verified immediately after. Any mutation outside the candidate scratch directory terminates execution fail-closed.
- **Static Defense-in-Depth:** Scans for forbidden escape tokens (`sorry`, `admit`, `native_decide`, `axiom`), host OS manipulations (`IO.FS`, `IO.Process`), and debug escape hatches (`set_option debug.*`).

---

## 4. Adversarial Regression Suite & Security Fixtures

The protocol enforces fail-closed security across dedicated adversarial regression fixtures:

| Fixture File | Attack Vector Tested | Result |
|---|---|---|
| `fixtures/security/elab_rules_eval_hijack.lean` | Intercepts `#eval!` via `elab_rules : command` to forge sentinel output | **REJECTED (exit code 1)**. `leanchecker` passes, but compiled `verifier` executable ignores custom command elaborator and evaluates proof term. |
| `fixtures/security/macro_rules_eval_hijack.lean` | Rewrites `#eval!` via `macro_rules` syntax expansion | **REJECTED (exit code 1)**. Compiled binary does not expand syntax macros on verification commands. |
| `fixtures/security/skip_kernel_tc.lean` | Sets `set_option debug.skipKernelTC true` to smuggle ill-typed proofs | **REJECTED (exit code 1)** by `leanchecker` during kernel replay. |
| `fixtures/security/run_cmd_fs_write.lean` | Executes IO during compilation via `run_cmd` to mutate repository | **REJECTED (exit code 1)** by static scan and filesystem integrity guard. |
| `fixtures/security/run_cmd_meta_cheat.lean` | Uses `run_cmd` meta-programming to alter environment | **REJECTED (exit code 1)** by static scan. |
| `fixtures/lifted/aux_escape_circular.lean` | Smuggles bridge dependency under `_aux` identifier | **REJECTED (exit code 1)** by module index provenance. |
| `fixtures/lifted/root_aux_circular.lean` | Escapes namespace into `_root_.aux` | **REJECTED (exit code 1)** by module index provenance. |
| `fixtures/method_mode/aux_escape_forbidden.lean` | Uses prohibited terminal lemma inside `_aux` helper | **REJECTED (exit code 1)** by module index provenance. |

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

- [x] **Gate 0:** Repository initialized with checked-in Lake project and standalone compiled adjudicator (`.lake/build/bin/verifier`).
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
- **Amendment 0.8 $\to$ 0.9:**
  - Independent Module Compilation (`CandidateDModule.lean`, `CandidateSModule.lean`, `CandidateLModule.lean`).
  - Mandatory kernel replay via `leanchecker`.
  - Process & filesystem snapshot guards against unauthorized host mutations.
- **Amendment 0.9 $\to$ 0.10 (Current):**
  - **Compiled Verifier Adjudicator Executable:** Completely eliminated host-side Lean source script elaboration (`#eval!`) after candidate module loading. Replaced with standalone native compiled binary (`.lake/build/bin/verifier`) that loads module `.olean` files as pure data via `Lean.importModules` and invokes `MetaM` verification natively.
  - **Immunity to Syntax & Command Hijacking:** Renders candidate-authored `elab_rules`, `macro_rules`, notation, and attribute overrides completely inert against the verifier.
  - **Structured Verification Receipts & Exit Codes:** Verification outcomes are communicated via POSIX exit codes (0 for PASS, 1 for FAIL) and machine-readable JSON receipts.
  - **Explicit TCB Specification:** Formally tabulated the Trusted Computing Base vs. Untrusted components.
  - **Accurate Sandbox Terminology:** Defined execution security boundary as *process hardening and mutation detection* to reflect exact host OS containment mechanics.
  - **Adversarial Hijack Fixtures:** Added `elab_rules_eval_hijack.lean` and `macro_rules_eval_hijack.lean` with regression test asserting that kernel-passing candidate elaborators cannot alter verifier execution.
