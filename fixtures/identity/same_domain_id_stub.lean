abbrev LiftDom := Nat
abbrev LiftCod := Nat

def liftT (n : LiftDom) : LiftCod := id n

theorem preservation_bridge (m : Nat) : (m + 0 = m) ↔ (liftT m + 0 = liftT m) := by
  sorry
