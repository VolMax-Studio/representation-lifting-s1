import Mathlib

abbrev LiftDom := ℕ
abbrev LiftCod := ℕ × Unit

def liftT (n : LiftDom) : LiftCod := (n, ())

def foo (p : LiftCod) : Prop := p.1 > 0
def bar (p : LiftCod) : Prop := p.1 = 0

-- Fails because neither side matches target conclusion (n + 0 = n)
theorem preservation_bridge (n : ℕ) : foo (liftT n) ↔ bar (liftT n) := by
  sorry
