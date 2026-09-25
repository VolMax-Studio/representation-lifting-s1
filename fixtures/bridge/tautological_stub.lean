import Mathlib

abbrev LiftDom := ℕ
abbrev LiftCod := ℕ × Unit

def liftT (n : LiftDom) : LiftCod := (n, ())

-- Fails because bridge is P ↔ P without referencing liftT
theorem preservation_bridge (n : ℕ) : (n + 0 = n) ↔ (n + 0 = n) := by
  sorry
