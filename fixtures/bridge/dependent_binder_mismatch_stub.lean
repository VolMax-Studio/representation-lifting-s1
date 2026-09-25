abbrev LiftDom := Nat
abbrev LiftCod := Nat × Unit

def liftT (n : LiftDom) : LiftCod := (n, ())

-- Fails because binder 1 has type (Fin (m + 1)) instead of (Fin m)
theorem preservation_bridge (m : Nat) (q : Fin (m + 1)) :
    (q.1 = q.1) ↔ (liftT m = liftT m) := by
  sorry
