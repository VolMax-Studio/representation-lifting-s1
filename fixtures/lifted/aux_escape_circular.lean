-- fixtures/lifted/aux_escape_circular.lean
-- Adversarial fixture: Attempts to hide circular dependency on preservation_bridge behind a `_aux` name prefix.
-- In v0.8 this escaped because `_aux` was trusted. In v0.9, module provenance catches it.

theorem preservation_bridge : BridgeProp := by
  intro m
  rfl

theorem _aux_circular_helper : LiftedClaim := by
  intro m
  have h := (preservation_bridge m).mp
  rfl

theorem lifted_theorem : LiftedClaim :=
  _aux_circular_helper
