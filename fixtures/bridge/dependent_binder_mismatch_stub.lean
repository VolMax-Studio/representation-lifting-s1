abbrev LiftDom := Nat
abbrev LiftCod := Nat × Unit

def liftT (n : LiftDom) : LiftCod := (n, ())

def LiftedClaim : Prop :=
  ∀ (m : Nat) (q : Fin (m + 1)), liftT m = liftT m

-- Fails because binder 1 has type (Fin (m + 1)) instead of (Fin m)
def BridgeProp : Prop :=
  ∀ (m : Nat) (q : Fin (m + 1)), (q.1 = q.1) ↔ (liftT m = liftT m)
