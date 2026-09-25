abbrev LiftDom := Nat
abbrev LiftCod := Nat × Unit

def liftT (n : LiftDom) : LiftCod := (n, ())

def invariant (p : LiftCod) : Nat := p.1

def LiftedClaim : Prop :=
  ∀ (m : Nat) (hm : 100 < m), invariant (liftT m) + 0 = invariant (liftT m)

-- Fails because binder 1 has type (100 < m) instead of (2 <= m)
def BridgeProp : Prop :=
  ∀ (m : Nat) (hm : 100 < m), (m + 0 = m) ↔ (invariant (liftT m) + 0 = invariant (liftT m))
