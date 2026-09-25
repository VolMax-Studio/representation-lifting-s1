abbrev LiftDom := Unit
abbrev LiftCod := Nat

def liftT (_ : LiftDom) : LiftCod := 11

theorem preservation_bridge : Exists (fun x : Nat => x > 10) ↔ (liftT () > 10) := by
  sorry
