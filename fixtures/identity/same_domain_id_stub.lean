abbrev LiftDom := Nat
abbrev LiftCod := Nat

def liftT (n : LiftDom) : LiftCod := id n

def BridgeProp : Prop :=
  ∀ (m : Nat), (m + 0 = m) ↔ (liftT m + 0 = liftT m)
