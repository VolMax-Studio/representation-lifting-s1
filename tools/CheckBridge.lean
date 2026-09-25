import Lean

/-!
tools/CheckBridge.lean
Pure Lean 4 meta-checker for Representation Search (Role S) Verification:
1. Strict Module Provenance:
   Candidate declarations are identified strictly by module index (`idx(candModName)`).
   Zero reliance on name prefixes, namespaces, `_root_`, `_aux`, or allowlists.
2. Method Mode Deny-List Enforcement:
   Recursively inspects direct constant references in all declarations authored in candidate module.
3. Pure Representation Axiom Audit across ALL Candidate Declarations (zero sorryAx):
   ALL candidate declarations must depend ONLY on {propext, Classical.choice, Quot.sound}.
4. Identity Guard (AND semantics):
   Evaluates whether LiftDom = LiftCod AND liftT = id definitionally.
   Rejects with IDENTITY_GUARD if both are true.
5. Sequential Dependent Binder Type Comparison:
   Peels binders of BridgeProp.value and frozen_target.type.
   Compares binder counts and types sequentially with replaceFVars.
6. Structural Target and LiftedClaim Linkage:
   Asserts conclusion of BridgeProp is an equivalence (↔).
   Rejects syntactically tautological equivalences (P ↔ P).
   Asserts one side matches target conclusion, other side matches LiftedClaim and contains liftT.
7. Sentinel: `CHECK_BRIDGE_SENTINEL_OK`.
Part of representation-lifting-s1 experimental protocol (v0.9).
-/

namespace VerifierTrustCore

set_option linter.unusedVariables false

open Lean Meta

def hasConstRef (e : Expr) (targetConst : Name) : Bool :=
  e.foldConsts false (fun name acc => acc || (name == targetConst))

def getDeclValue? (decl : ConstantInfo) : Option Expr :=
  match decl with
  | .thmInfo v => some v.value
  | .defnInfo v => some v.value
  | _ => none

def isProhibited (c : Name) (prohibited : List Name) : Bool :=
  prohibited.any fun p => p == c || p.isPrefixOf c

def checkDirectProhibited (env : Environment) (declNames : List Name) (prohibited : List Name) : MetaM Unit := do
  if prohibited.isEmpty then return ()
  for d in declNames do
    if let some decl := env.find? d then
      if let some val := getDeclValue? decl then
        let consts := val.foldConsts [] (fun c acc => if acc.contains c then acc else c :: acc)
        for c in consts do
          if isProhibited c prohibited then
            throwError s!"FORBIDDEN_METHOD_MODE_CONSTANT: Declaration '{d}' directly references prohibited constant '{c}'."

def resolveInModule (env : Environment) (modIdx : ModuleIdx) (targetShortName : String) : MetaM Name := do
  let consts := env.header.moduleData[modIdx.toNat]!.constants
  for c in consts do
    if match c.name with | .str _ s => s == targetShortName | _ => false then
      return c.name
  throwError s!"Declaration '{targetShortName}' not found in candidate module."

def runCheckBridge (candModName frozenTargetName : Name) (prohibited : List Name) : MetaM Unit := do
  let env ← getEnv
  
  -- 1. Locate Candidate Module
  let some candIdx := env.getModuleIdx? candModName
    | throwError s!"Candidate module '{candModName}' not found in environment."
  
  let candidateConsts := env.header.moduleData[candIdx.toNat]!.constants
  let candidateDecls := candidateConsts.map (·.name) |>.toList
  
  -- 2. Method Mode Deny-List Audit across ALL candidate declarations
  checkDirectProhibited env candidateDecls prohibited

  -- 3. Resolve Structural Declarations inside Candidate Module
  let some targetDecl := env.find? frozenTargetName 
    | throwError s!"Target declaration '{frozenTargetName}' not found in environment."
  
  let bPropResolved ← resolveInModule env candIdx "BridgeProp"
  let lClaimResolved ← resolveInModule env candIdx "LiftedClaim"
  let liftTResolved ← resolveInModule env candIdx "liftT"
  let domResolved ← resolveInModule env candIdx "LiftDom"
  let codResolved ← resolveInModule env candIdx "LiftCod"

  let some (.defnInfo bridgePropVal) := env.find? bPropResolved 
    | throwError s!"Declaration '{bPropResolved}' is not a definition."
  let some (.defnInfo liftedClaimVal) := env.find? lClaimResolved 
    | throwError s!"Declaration '{lClaimResolved}' is not a definition."
  let some liftTDecl := env.find? liftTResolved 
    | throwError s!"Declaration '{liftTResolved}' not found."
  let some _ := env.find? domResolved 
    | throwError s!"Declaration '{domResolved}' not found."
  let some _ := env.find? codResolved 
    | throwError s!"Declaration '{codResolved}' not found."

  -- 4. Pure Representation Axiom Audit across ALL Candidate Declarations (zero sorryAx)
  let allowedAxioms : List Name := [`propext, `Classical.choice, `Quot.sound]
  for d in candidateDecls do
    let axioms ← Lean.collectAxioms d
    for ax in axioms do
      if !allowedAxioms.contains ax then
        throwError s!"FORBIDDEN_AXIOM: Specification declaration '{d}' relies on non-standard axiom '{ax}'."

  -- 5. Identity Guard (AND Semantics: LiftDom = LiftCod AND liftT = id)
  let domEqCod ← isDefEq (mkConst domResolved) (mkConst codResolved)
  if domEqCod then
    let idFn ← mkAppOptM ``id #[some (mkConst domResolved)]
    let isId ← isDefEq (mkConst liftTResolved) idFn
    if isId then
      throwError "IDENTITY_GUARD: Representation map is definitionally the identity function on identical domains."

  -- 6. Target Linkage & Sequential Dependent Binder Comparison
  forallTelescope targetDecl.type fun targetVars targetConcl => do
    forallTelescope bridgePropVal.value fun bridgeVars bridgeConcl => do
      -- Check binder count
      if targetVars.size != bridgeVars.size then
        throwError s!"BINDER_COUNT_MISMATCH: Target has {targetVars.size} binders, bridge prop has {bridgeVars.size} binders."

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
      let lhsMatchesTarget ← isDefEq lhs targetConcl
      let rhsMatchesTarget ← isDefEq rhs targetConcl

      if !lhsMatchesTarget && !rhsMatchesTarget then
        throwError s!"UNLINKED_TARGET: Neither side of bridge matches target conclusion:\n  Target: {targetConcl}\n  LHS: {lhs}\n  RHS: {rhs}"

      let liftedSide := if lhsMatchesTarget then rhs else lhs
      if !hasConstRef liftedSide liftTResolved then
        throwError s!"UNLIFTED_BRIDGE: Lifted side does not contain constant '{liftTResolved}':\n  {liftedSide}"

      -- Verify that liftedSide matches LiftedClaim peeled conclusion
      forallTelescope liftedClaimVal.value fun claimVars claimConcl => do
        if claimVars.size != targetVars.size then
          throwError s!"CLAIM_BINDER_COUNT_MISMATCH: LiftedClaim has {claimVars.size} binders, expected {targetVars.size}."
        let claimConclSubst := claimConcl.replaceFVars claimVars targetVars
        if !(← isDefEq liftedSide claimConclSubst) then
          throwError s!"UNLINKED_LIFTED_CLAIM: Lifted side of bridge does not match LiftedClaim:\n  Bridge lifted side: {liftedSide}\n  LiftedClaim: {claimConclSubst}"

      IO.println "CHECK_BRIDGE_SENTINEL_OK"

end VerifierTrustCore
