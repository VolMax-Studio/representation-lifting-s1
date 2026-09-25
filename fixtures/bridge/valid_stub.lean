abbrev LiftDom := Nat
abbrev LiftCod := Nat × Unit

def liftT (n : LiftDom) : LiftCod := (n, ())

def invariant (p : LiftCod) : Nat := p.1

theorem preservation_bridge (m : Nat) : (m + 0 = m) ↔ (invariant (liftT m) + 0 = invariant (liftT m)) := by
  sorry
