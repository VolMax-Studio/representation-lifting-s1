import Mathlib.Data.Int.Fib.Lemmas

theorem frozen_target (n : ℕ) (hn : 1 ≤ n) :
    (Nat.fib (n + 1) : ℤ) * (Nat.fib (n - 1) : ℤ) - (Nat.fib n : ℤ)^2 = (-1)^n := by sorry
