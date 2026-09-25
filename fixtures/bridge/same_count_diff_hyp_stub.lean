abbrev LiftDom := Nat
abbrev LiftCod := Nat × Unit

def liftT (n : LiftDom) : LiftCod := (n, ())

def invariant (p : LiftCod) : Nat := p.1

-- Fails because binder 1 has type (100 < m) instead of (2 <= m)
theorem preservation_bridge (m : Nat) (hm : 100 < m) :
    (m + 0 = m) ↔ (invariant (liftT m) + 0 = invariant (liftT m)) := by
  sorry
