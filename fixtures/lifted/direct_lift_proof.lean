theorem preservation_bridge : BridgeProp := by
  intro m
  rfl

theorem executor_theorem (n : Nat) : n + 0 = n := by
  have h := (preservation_bridge n).mpr rfl
  exact h
