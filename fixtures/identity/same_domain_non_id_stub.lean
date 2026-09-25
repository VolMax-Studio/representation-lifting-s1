abbrev LiftDom := Nat
abbrev LiftCod := Nat

def liftT (n : LiftDom) : LiftCod := n + 1

def LiftedClaim : Prop :=
  ∀ (m : Nat), liftT m + 0 = liftT m

def BridgeProp : Prop :=
  ∀ (m : Nat), (m + 0 = m) ↔ (liftT m + 0 = liftT m)
