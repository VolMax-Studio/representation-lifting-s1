abbrev LiftDom := Nat
abbrev LiftCod := Nat

def liftT (n : LiftDom) : LiftCod := n + 1

theorem preservation_bridge (m : Nat) : (m + 0 = m) ↔ (liftT m + 0 = liftT m) := by
  sorry
