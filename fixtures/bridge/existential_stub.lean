abbrev LiftDom := Unit
abbrev LiftCod := Nat

def liftT (_ : LiftDom) : LiftCod := 11

def LiftedClaim : Prop :=
  liftT () > 10

def BridgeProp : Prop :=
  Exists (fun x : Nat => x > 10) ↔ (liftT () > 10)
