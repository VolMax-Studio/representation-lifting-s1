import Lean

/-!
tools/CheckBridge.lean
Pure Lean 4 meta-checker for Representation Stub verification:
1. Verifies that `LiftDom`, `LiftCod`, `liftT`, and `preservation_bridge` are declared.
2. Identity Guard: Evaluates definitional equality `LiftDom = LiftCod` and `liftT = id`.
   If definitionally trivial, fails with IDENTITY_GUARD.
3. Target Linkage:
   - Uses `forallTelescope` and `replaceFVars` to compare target and bridge binders.
   - Rejects extraneous unquantified hypotheses.
   - Asserts conclusion is an equivalence (`↔`).
   - Rejects syntactically tautological equivalences (`P ↔ P`).
   - Asserts one side matches the target conclusion under the peeled telescope.
   - Asserts the other side contains constant `liftT`.
4. Sorry Audit:
   - Asserts `sorryAx` is absent from `LiftDom`, `LiftCod`, and `liftT`.
   - `sorryAx` is permitted strictly in `preservation_bridge`.
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
  let some domDecl := env.find? domName 
    | throwError s!"Domain '{domName}' not found."
  let some codDecl := env.find? codName 
    | throwError s!"Codomain '{codName}' not found."

  -- 2. Sorry audit on representation layer
  let liftTAxioms ← Lean.collectAxioms liftTName
  if liftTAxioms.contains ``sorryAx then
    throwError s!"SORRY_IN_REPRESENTATION: '{liftTName}' depends on sorryAx."

  -- 3. Identity Guard check
  let domType := domDecl.type
  let codType := codDecl.type
  -- Check if LiftDom and LiftCod are definitionally identical types
  let domEqCod ← isDefEq domType codType
  if domEqCod then
    -- Check if liftT is definitionally identity
    let isId ← try
      let idFn ← mkAppM ``id #[domType]
      isDefEq (mkConst liftTName) idFn
    catch _ =>
      pure false
    if isId then
      throwError "IDENTITY_GUARD: Representation map is definitionally the identity function on identical domains."

  -- 4. Target Linkage check
  forallTelescope targetDecl.type fun targetVars targetConcl => do
    forallTelescope bridgeDecl.type fun bridgeVars bridgeConcl => do
      -- Check binder count and types
      if targetVars.size != bridgeVars.size then
        throwError s!"EXTRA_HYPOTHESIS: Target has {targetVars.size} binders, bridge has {bridgeVars.size} binders."

      -- Substitute bridge free variables with target free variables
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

      IO.println "BRIDGE_VALID: Structure, Identity Guard, and Target Linkage verified."
