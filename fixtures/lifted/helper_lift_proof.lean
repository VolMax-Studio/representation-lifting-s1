theorem preservation_bridge : BridgeProp := by
  intro m
  rfl

theorem helper_lemma (k : Nat) : k + 0 = k := by
  exact (preservation_bridge k).mpr rfl

theorem executor_theorem (n : Nat) : n + 0 = n := by
  exact helper_lemma n
