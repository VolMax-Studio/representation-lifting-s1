import Mathlib.Data.Nat.Fib.Basic

end CandidateExecutor

theorem escaped_forbidden (m n : ℕ) :
    Nat.fib (m + n + 1) = Nat.fib m * Nat.fib n + Nat.fib (m + 1) * Nat.fib (n + 1) :=
  Nat.fib_add m n

namespace CandidateExecutor

theorem executor_theorem (m n : ℕ) :
    Nat.fib (m + n + 1) = Nat.fib m * Nat.fib n + Nat.fib (m + 1) * Nat.fib (n + 1) :=
  escaped_forbidden m n
