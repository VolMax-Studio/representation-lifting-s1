import Mathlib

open Filter Set TopologicalSpace
open scoped Topology

def is_topology (X : Type*) (T : Set (Set X)) :=
  univ ∈ T ∧
  (∀ s t, s ∈ T → t ∈ T → s ∩ t ∈ T) ∧
  (∀s, (∀t ∈ s, t ∈ T) → sUnion s ∈ T)

theorem frozen_target {X : Type*}
  (A : Set (Set X))
  (hcover : ∀ x : X, ∃ B ∈ A, x ∈ B)
  (hrefine : ∀ B₁ ∈ A, ∀ B₂ ∈ A, ∀ x ∈ B₁ ∩ B₂, ∃ B₃ ∈ A, x ∈ B₃ ∧ B₃ ⊆ B₁ ∩ B₂) :
  {U : Set X | @IsOpen X (generateFrom A) U}
    =
  sInter {T : Set (Set X) | is_topology X T ∧ A ⊆ T} := by sorry
