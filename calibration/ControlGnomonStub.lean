/-
calibration/ControlGnomonStub.lean
Pre-frozen lifted representation stub for Negative Control: sum of odd numbers = n^2.
Part of the representation-lifting-s1 experimental protocol (v0.6).
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

/-- Closed proposition on lifted gnomon grid representation -/
def LiftedClaim : Prop :=
  ∀ (n : ℕ), invariant (liftT n) = n^2 ∧ invariant (liftT n) = ∑ k ∈ Finset.range n, (2 * k + 1)

/-- Preservation bridge property linking target summation identity to decomposition of liftT n -/
def BridgeProp : Prop :=
  ∀ (n : ℕ),
    (∑ k ∈ Finset.range n, (2 * k + 1) = n^2) ↔
    (invariant (liftT n) = n^2 ∧ invariant (liftT n) = ∑ k ∈ Finset.range n, (2 * k + 1))
