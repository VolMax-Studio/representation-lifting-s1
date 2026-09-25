theorem preservation_bridge : BridgeProp := by
  intro m
  rfl

theorem helper_lemma (k : Nat) : (liftT k).1 + 0 = (liftT k).1 := by
  rfl

theorem lifted_theorem : LiftedClaim := by
  intro m
  exact helper_lemma m
