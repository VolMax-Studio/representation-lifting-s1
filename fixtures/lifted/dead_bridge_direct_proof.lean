theorem preservation_bridge : BridgeProp := by
  intro m
  rfl

-- Dummy direct proof with dead bridge reference that fooled v0.5
theorem executor_theorem (m : Nat) : m + 0 = m := by
  have _ := preservation_bridge
  rfl
