theorem preservation_bridge : BridgeProp := by
  intro m
  rfl

theorem helper_bridge : BridgeProp := preservation_bridge

theorem lifted_theorem : LiftedClaim := by
  intro m
  have _ := helper_bridge m
  rfl
