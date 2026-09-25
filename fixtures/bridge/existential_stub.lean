import Mathlib

abbrev LiftDom := Unit
abbrev LiftCod := ℕ

def liftT (_ : LiftDom) : LiftCod := 11

theorem preservation_bridge : (∃ x : ℕ, x > 10) ↔ (liftT () > 10) := by
  sorry
