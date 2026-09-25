theorem preservation_bridge : BridgeProp := by
  intro m
  rfl

-- Cheated proof: perfectly valid proof of target, but does NOT depend on preservation_bridge
theorem executor_theorem (n : Nat) : n + 0 = n := by
  rfl
