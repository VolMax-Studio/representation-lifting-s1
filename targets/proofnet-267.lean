import Mathlib

open Fintype Set Real Ideal Polynomial
open scoped BigOperators



theorem frozen_target {G : Type*} [Group G] {p : ℕ} (hp : Nat.Prime p)
  {P : Sylow p G} (hP : P.Normal) :
  Subgroup.Characteristic (P : Subgroup G) := by sorry
