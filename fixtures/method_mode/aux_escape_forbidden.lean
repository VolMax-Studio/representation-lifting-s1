-- fixtures/method_mode/aux_escape_forbidden.lean
-- Adversarial fixture: Attempts to hide a prohibited library constant behind a `_aux` name prefix.
-- In v0.8 this escaped because `_aux` was trusted. In v0.9, module provenance catches it.

import Mathlib.Data.Nat.Fib.Basic

theorem _aux_forbidden (m n : ℕ) :
    Nat.fib (m + n + 1) = Nat.fib m * Nat.fib n + Nat.fib (m + 1) * Nat.fib (n + 1) :=
  Nat.fib_add m n

theorem executor_theorem (m n : ℕ) :
    Nat.fib (m + n + 1) = Nat.fib m * Nat.fib n + Nat.fib (m + 1) * Nat.fib (n + 1) :=
  _aux_forbidden m n
