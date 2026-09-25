import Mathlib

abbrev LiftDom := ℕ
abbrev LiftCod := ℕ × Unit

def liftT (n : LiftDom) : LiftCod := (n, ())

-- Fails because bridge introduces an extra hypothesis (h_extra : n > 100) not present in target
theorem preservation_bridge (n : ℕ) (h_extra : n > 100) :
    (n + 0 = n) ↔ ((liftT n).1 + 0 = (liftT n).1) := by
  sorry
