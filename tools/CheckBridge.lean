import Lean

/-!
tools/CheckBridge.lean
Pure Lean 4 meta-checker for Representation Stub verification:
1. Verifies that `LiftDom`, `LiftCod`, `liftT`, and `preservation_bridge` are declared.
2. Representation Axiom Audit:
   - LiftDom, LiftCod, liftT must depend ONLY on {propext, Classical.choice, Quot.sound}.
   - Rejects sorryAx or custom axioms in the representation layer.
   - preservation_bridge may depend on {propext, Classical.choice, Quot.sound, sorryAx}.
3. Identity Guard (AND semantics):
   - Evaluates whether LiftDom = LiftCod AND liftT = id definitionally.
   - Rejects with IDENTITY_GUARD only if both are true.
4. Sequential Dependent Binder Type Comparison:
   - Compares binder counts and types sequentially with replaceFVars.
   - Rejects extraneous or mismatched hypotheses (e.g. 2 <= n vs 100 < n).
5. Target Linkage:
   - Asserts conclusion is an equivalence (↔).
   - Rejects syntactically tautological equivalences (P ↔ P).
   - Asserts one side matches target conclusion under the peeled telescope.
   - Asserts the other side contains constant `liftT`.
6. Prints strict sentinel: `CHECK_BRIDGE_SENTINEL_OK`.
Part of representation-lifting-s1 experimental protocol.
-/

open Lean Meta

def hasConstRef (e : Expr) (targetConst : Name) : Bool :=
  e.foldConsts false (fun name acc => acc || (name == targetConst))

def runCheckBridge (targetName bridgeName liftTName domName codName : Name) : MetaM Unit := do
  let env ← getEnv
  
  -- 1. Structural declaration check
  let some targetDecl := env.find? targetName 
    | throwError s!"Target declaration '{targetName}' not found."
  let some bridgeDecl := env.find? bridgeName 
    | throwError s!"Bridge declaration '{bridgeName}' not found."
  let some liftTDecl := env.find? liftTName 
    | throwError s!"Representation map '{liftTName}' not found."
  let some _ := env.find? domName 
    | throwError s!"Domain '{domName}' not found."
  let some _ := env.find? codName 
    | throwError s!"Codomain '{codName}' not found."

  -- 2. Representation Axiom Audit (fail-closed, no custom axioms, no sorryAx in rep layer)
  let allowedRepAxioms : List Name := [`propext, `Classical.choice, `Quot.sound]
  for cName in [domName, codName, liftTName] do
    let axioms ← Lean.collectAxioms cName
    for ax in axioms do
      if !allowedRepAxioms.contains ax then
        throwError s!"FORBIDDEN_REPRESENTATION_AXIOM: '{cName}' transitively depends on axiom '{ax}'."

  let allowedBridgeAxioms : List Name := [`propext, `Classical.choice, `Quot.sound, `sorryAx]
  let bridgeAxioms ← Lean.collectAxioms bridgeName
  for ax in bridgeAxioms do
    if !allowedBridgeAxioms.contains ax then
      throwError s!"FORBIDDEN_BRIDGE_AXIOM: '{bridgeName}' transitively depends on axiom '{ax}'."

  -- 3. Identity Guard (AND semantics: LiftDom = LiftCod AND liftT = id)
  let domEqCod ← isDefEq (mkConst domName) (mkConst codName)
  if domEqCod then
    let idFn ← mkAppOptM ``id #[some (mkConst domName)]
    let isId ← isDefEq (mkConst liftTName) idFn
    if isId then
      throwError "IDENTITY_GUARD: Representation map is definitionally the identity function on identical domains."

  -- 4. Target Linkage & Sequential Dependent Binder Comparison
  forallTelescope targetDecl.type fun targetVars targetConcl => do
    forallTelescope bridgeDecl.type fun bridgeVars bridgeConcl => do
      -- Check binder count
      if targetVars.size != bridgeVars.size then
        throwError s!"BINDER_COUNT_MISMATCH: Target has {targetVars.size} binders, bridge has {bridgeVars.size} binders."

      -- Check binder types sequentially with dependent substitution
      for i in [:targetVars.size] do
        let tVar := targetVars[i]!
        let bVar := bridgeVars[i]!
        let tType ← inferType tVar
        let bType ← inferType bVar
        let bTypeSubst := bType.replaceFVars (bridgeVars.extract 0 i) (targetVars.extract 0 i)
        if !(← isDefEq tType bTypeSubst) then
          throwError s!"BINDER_TYPE_MISMATCH: Binder {i} type mismatch: target expects {tType}, bridge has {bTypeSubst}"

      -- Substitute bridge free variables with target free variables in conclusion
      let bridgeConclSubst := bridgeConcl.replaceFVars bridgeVars targetVars

      -- Check that conclusion is an Iff (↔)
      let some (lhs, rhs) := bridgeConclSubst.iff? 
        | throwError s!"NON_EQUIVALENCE_BRIDGE: Bridge conclusion is not an equivalence (↔): {bridgeConclSubst}"

      -- Tautology check
      if lhs == rhs then
        throwError s!"TAUTOLOGICAL_BRIDGE: Bridge equivalence is syntactically tautological ({lhs} ↔ {rhs})."

      -- Match one side against target conclusion
      let lhsMatches ← isDefEq lhs targetConcl
      let rhsMatches ← isDefEq rhs targetConcl

      if !lhsMatches && !rhsMatches then
        throwError s!"UNLINKED_TARGET: Neither side of bridge matches target conclusion:\n  Target: {targetConcl}\n  LHS: {lhs}\n  RHS: {rhs}"

      let liftedSide := if lhsMatches then rhs else lhs
      if !hasConstRef liftedSide liftTName then
        throwError s!"UNLIFTED_BRIDGE: Lifted side does not contain constant '{liftTName}':\n  {liftedSide}"

      IO.println "CHECK_BRIDGE_SENTINEL_OK"
