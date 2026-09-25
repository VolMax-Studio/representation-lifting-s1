import Mathlib

abbrev LiftDom := ℕ
abbrev LiftCod := ℕ × Unit

def liftT (n : LiftDom) : LiftCod := (n, ())

def invariant (p : LiftCod) : ℕ := p.1

theorem preservation_bridge (n : ℕ) : (n + 0 = n) ↔ (invariant (liftT n) + 0 = invariant (liftT n)) := by
  sorry
