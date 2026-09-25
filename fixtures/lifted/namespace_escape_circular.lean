theorem preservation_bridge : BridgeProp := by
  intro m
  rfl

end CandidateExecutor

theorem escaped_circular : LiftedClaim := by
  intro m
  have _ := CandidateExecutor.preservation_bridge m
  rfl

namespace CandidateExecutor

theorem lifted_theorem : LiftedClaim := escaped_circular
