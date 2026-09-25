import Mathlib.Algebra.Group.Basic

theorem executor_theorem {G : Type} [AddCommGroup G] (a b : G) : a + b = b + a := by
  exact add_comm a b
