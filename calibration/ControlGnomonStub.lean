/-
calibration/ControlGnomonStub.lean
Pre-frozen lifted representation stub for Negative Control: sum of odd numbers = n^2.
Part of the representation-lifting-s1 experimental protocol.
-/

import Mathlib

abbrev LiftDom := ℕ
abbrev LiftCod := Finset (ℕ × ℕ)

/-- Gnomon/Square grid representation mapping n to n × n coordinate grid -/
def liftT (n : LiftDom) : LiftCod :=
  Finset.range n ×ˢ Finset.range n

/-- Structural invariant: cardinality of the product grid -/
def invariant (s : LiftCod) : ℕ :=
  s.card

/-- Preservation bridge linking target summation identity to decomposition of liftT n -/
theorem preservation_bridge_sum_odd_sq (n : ℕ) :
    (∑ k ∈ Finset.range n, (2 * k + 1) = n^2) ↔
    (invariant (liftT n) = n^2 ∧ invariant (liftT n) = ∑ k ∈ Finset.range n, (2 * k + 1)) := by
  sorry
