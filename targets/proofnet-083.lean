import Mathlib

open Fintype Set Real Ideal Polynomial
open scoped BigOperators



theorem frozen_target {p : ℕ} {n : ℕ} {G : Type*} [Fintype G]
  [Group G] (hp : Nat.Prime p) (hG : card G = p ^ n) {K : Subgroup G}
  [Fintype K] (hK : card K = p ^ (n-1)) :
  K.Normal := by sorry
