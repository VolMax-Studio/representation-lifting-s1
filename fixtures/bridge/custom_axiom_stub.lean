abbrev LiftDom := Nat
abbrev LiftCod := Nat × Unit

axiom magic_map : LiftDom → LiftCod

noncomputable def liftT (n : LiftDom) : LiftCod := magic_map n

-- Fails because liftT relies on custom axiom magic_map
theorem preservation_bridge (m : Nat) : (m + 0 = m) ↔ ((liftT m).1 + 0 = (liftT m).1) := by
  sorry
