abbrev LiftDom := Nat
abbrev LiftCod := Nat × Unit

def liftT (n : LiftDom) : LiftCod := (n, ())

-- Fails because LHS and RHS are syntactically identical (P ↔ P)
def BridgeProp : Prop :=
  ∀ (m : Nat), (m + 0 = m) ↔ (m + 0 = m)
