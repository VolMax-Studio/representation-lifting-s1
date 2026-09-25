import Mathlib.Data.Int.Fib.Lemmas

theorem executor_theorem (n : ℕ) (hn : 1 ≤ n) :
    (Nat.fib (n + 1) : ℤ) * (Nat.fib (n - 1) : ℤ) - (Nat.fib n : ℤ)^2 = (-1)^n := by
  have _ := Int.fib_succ_mul_fib_pred_sub_fib_sq
  sorry
