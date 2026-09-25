abbrev LiftDom := Nat
abbrev LiftCod := Nat × Unit

def liftT (n : LiftDom) : LiftCod := (n, ())

def invariant (p : LiftCod) : Nat := p.1

def LiftedClaim : Prop :=
  ∀ (m : Nat), invariant (liftT m) + 0 = invariant (liftT m)

def BridgeProp : Prop :=
  ∀ (m : Nat), (m + 0 = m) ↔ (invariant (liftT m) + 0 = invariant (liftT m))
