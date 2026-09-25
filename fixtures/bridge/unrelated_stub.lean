abbrev LiftDom := Nat
abbrev LiftCod := Nat × Unit

def liftT (n : LiftDom) : LiftCod := (n, ())

def foo (p : LiftCod) : Prop := p.1 > 0
def bar (p : LiftCod) : Prop := p.1 = 0

def LiftedClaim : Prop :=
  ∀ (m : Nat), bar (liftT m)

-- Fails because neither side matches target conclusion (m + 0 = m)
def BridgeProp : Prop :=
  ∀ (m : Nat), foo (liftT m) ↔ bar (liftT m)
