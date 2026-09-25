import Mathlib.Algebra.Group.Basic

abbrev LiftDom := Unit
abbrev LiftCod := Unit × Unit

def liftT (_ : LiftDom) : LiftCod := ((), ())

def LiftedClaim : Prop :=
  ∀ {G : Type} [AddCommGroup G] (a b : G), (liftT () = ((), ())) ∧ a + b = b + a

def BridgeProp : Prop :=
  ∀ {G : Type} [AddCommGroup G] (a b : G), (a + b = b + a) ↔ ((liftT () = ((), ())) ∧ a + b = b + a)
