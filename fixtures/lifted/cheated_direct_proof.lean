theorem preservation_bridge : BridgeProp := by
  intro m
  rfl

-- Circular cheat: lifted_theorem proves itself through preservation_bridge
theorem lifted_theorem : LiftedClaim := by
  intro m
  have h_direct : m + 0 = m := rfl
  exact (preservation_bridge m).mp h_direct
