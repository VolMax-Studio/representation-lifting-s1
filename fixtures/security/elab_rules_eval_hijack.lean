import Lean
open Lean

/-!
fixtures/security/elab_rules_eval_hijack.lean
Adversarial security fixture for representation-lifting-s1 (v0.10).

Attempts to hijack the `#eval!` command elaborator using `elab_rules : command`.
In v0.9, the verifier script elaborated `#eval! runVerifyLifted ...` after importing the candidate,
allowing the candidate's custom elaborator to intercept execution and emit a fake sentinel.
In v0.10, the verifier is a standalone compiled binary (`.lake/build/bin/verifier`) that
loads modules directly into the `Environment` via `Lean.importModules` and invokes `MetaM`
APIs natively in C/machine code. Zero Lean syntax is elaborated after importing the candidate.
-/

elab_rules : command
  | `(#eval! $_) => Lean.logInfo "VERIFY_LIFTED_SENTINEL_OK"

theorem candidate_fake_thm (n : Nat) : n = n := by rfl
