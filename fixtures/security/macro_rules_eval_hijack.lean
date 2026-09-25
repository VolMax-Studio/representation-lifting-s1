import Lean
open Lean

/-!
fixtures/security/macro_rules_eval_hijack.lean
Adversarial security fixture for representation-lifting-s1 (v0.10).

Attempts to hijack `#eval!` syntax macro expansion using `macro_rules`.
In v0.9, if the checker elaborated `#eval! ...`, this macro could rewrite the command
to output a fake sentinel string.
In v0.10, the compiled verifier binary does not elaborate any command syntax after
importing candidate modules.
-/

macro_rules
  | `(#eval! $_) => `(#check "VERIFY_LIFTED_SENTINEL_OK")

theorem candidate_fake_thm (n : Nat) : n = n := by rfl
