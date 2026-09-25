theorem preservation_bridge : BridgeProp := by
  intro m
  rfl

theorem _root_.aux_circular : LiftedClaim := by
  intro m
  have _ := preservation_bridge m
  rfl

theorem lifted_theorem : LiftedClaim := aux_circular
