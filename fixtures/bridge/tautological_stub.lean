abbrev LiftDom := Nat
abbrev LiftCod := Nat × Unit

def liftT (n : LiftDom) : LiftCod := (n, ())

-- Fails because LHS and RHS are syntactically identical (P ↔ P)
theorem preservation_bridge (m : Nat) : (m + 0 = m) ↔ (m + 0 = m) := by
  sorry
