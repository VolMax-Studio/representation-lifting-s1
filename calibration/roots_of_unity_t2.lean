import Mathlib

theorem frozen_target (n : ℕ) (hn : 2 ≤ n) :
    ∑ k ∈ Finset.range n, Real.sin (2 * Real.pi * k / n) = 0 := by sorry
