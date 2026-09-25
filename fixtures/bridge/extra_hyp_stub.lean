abbrev LiftDom := Nat
abbrev LiftCod := Nat × Unit

def liftT (n : LiftDom) : LiftCod := (n, ())

-- Fails because bridge introduces an extra binder (h_extra : m > 100) not in target
def BridgeProp : Prop :=
  ∀ (m : Nat) (h_extra : m > 100), (m + 0 = m) ↔ ((liftT m).1 + 0 = (liftT m).1)
