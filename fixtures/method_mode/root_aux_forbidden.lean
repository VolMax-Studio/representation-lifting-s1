import Mathlib.Data.Nat.Fib.Basic

theorem _root_.aux_forbidden (m n : ℕ) :
    Nat.fib (m + n + 1) = Nat.fib m * Nat.fib n + Nat.fib (m + 1) * Nat.fib (n + 1) :=
  Nat.fib_add m n

theorem executor_theorem (m n : ℕ) :
    Nat.fib (m + n + 1) = Nat.fib m * Nat.fib n + Nat.fib (m + 1) * Nat.fib (n + 1) :=
  aux_forbidden m n
