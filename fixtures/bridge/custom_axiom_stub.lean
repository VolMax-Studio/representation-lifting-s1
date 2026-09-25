abbrev LiftDom := Nat
abbrev LiftCod := Nat × Unit

axiom magic_map : LiftDom → LiftCod

noncomputable def liftT (n : LiftDom) : LiftCod := magic_map n

def LiftedClaim : Prop :=
  ∀ (m : Nat), (liftT m).1 + 0 = (liftT m).1

-- Fails because liftT relies on custom axiom magic_map
def BridgeProp : Prop :=
  ∀ (m : Nat), (m + 0 = m) ↔ ((liftT m).1 + 0 = (liftT m).1)
