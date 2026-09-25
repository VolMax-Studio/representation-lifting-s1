import Mathlib

abbrev LiftDom := ℕ
abbrev LiftCod := Finset ℂ

def liftT (n : LiftDom) : LiftCod := Finset.range n

def invariant (s : LiftCod) : ℕ := s.card

theorem preservation_bridge (n : ℕ) (hn : 2 ≤ n) :
    (∑ k ∈ Finset.range n, Real.cos (2 * Real.pi * k / n) = 0) ↔ (invariant (liftT n) = n) := by
  sorry
