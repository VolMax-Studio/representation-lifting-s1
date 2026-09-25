import Lean

/-!
tools/CheckBridge.lean
Pure Lean 4 meta-checker for Representation Search (Role S) Verification:
1. Lean-Native Candidate Declaration Enumeration:
   Inspects environment for all declarations in `CandidateExecutor` namespace.
2. Verifies that `LiftDom`, `LiftCod`, `liftT`, `LiftedClaim`, and `BridgeProp` are declared.
3. Representation Axiom Audit (zero sorryAx, zero custom axioms):
   - ALL declarations authored in `CandidateExecutor` must depend ONLY on:
     {propext, Classical.choice, Quot.sound}.
   - Role S produces a proof-free specification; sorryAx anywhere is strictly forbidden.
4. Identity Guard (AND semantics):
   - Evaluates whether LiftDom = LiftCod AND liftT = id definitionally.
   - Rejects with IDENTITY_GUARD if both are true.
5. Sequential Dependent Binder Type Comparison:
   - Peels binders of BridgeProp.value and frozen_target.type.
   - Compares binder counts and types sequentially with replaceFVars.
   - Rejects extraneous or mismatched hypotheses.
6. Structural Target and LiftedClaim Linkage:
   - Asserts conclusion of BridgeProp is an equivalence (↔).
   - Rejects syntactically tautological equivalences (P ↔ P).
   - Asserts one side matches target conclusion under the peeled telescope.
   - Asserts the other side matches LiftedClaim conclusion under the peeled telescope.
   - Asserts the lifted side contains constant `liftT`.
7. Method Mode Deny-List Enforcement:
   - Recursively inspects direct constants in all candidate declarations against prohibited constants (exact and prefix).
8. Prints strict sentinel: `CHECK_BRIDGE_SENTINEL_OK`.
Part of representation-lifting-s1 experimental protocol (v0.7).
-/

set_option linter.unusedVariables false

open Lean Meta

partial def isCandidateDecl (n : Name) : Bool :=
  match n with
  | .anonymous => false
  | .str p s => if s == "CandidateExecutor" then true else isCandidateDecl p
  | .num p _ => isCandidateDecl p

def getCandidateDecls (env : Environment) : List Name :=
  env.constants.fold (fun acc name _ =>
    if isCandidateDecl name then name :: acc else acc
  ) []

def resolveCandidateName (env : Environment) (shortName : Name) : MetaM Name := do
  if env.contains shortName then
    return shortName
  let inNs := `CandidateExecutor ++ shortName
  if env.contains inNs then
    return inNs
  throwError s!"Declaration '{shortName}' (or '{inNs}') not found in environment."

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

def runCheckBridge (targetName bridgePropName liftedClaimName liftTName domName codName : Name) (prohibited : List Name) : MetaM Unit := do
  let env ← getEnv
  
  -- 1. Structural declaration check & Name resolution
  let some targetDecl := env.find? targetName 
    | throwError s!"Target declaration '{targetName}' not found."
  let bPropResolved ← resolveCandidateName env bridgePropName
  let lClaimResolved ← resolveCandidateName env liftedClaimName
  let liftTResolved ← resolveCandidateName env liftTName
  let domResolved ← resolveCandidateName env domName
  let codResolved ← resolveCandidateName env codName

  let some (.defnInfo bridgePropVal) := env.find? bPropResolved 
    | throwError s!"Bridge property definition '{bPropResolved}' not found or not a definition."
  let some (.defnInfo liftedClaimVal) := env.find? lClaimResolved 
    | throwError s!"Lifted claim definition '{lClaimResolved}' not found or not a definition."
  let some liftTDecl := env.find? liftTResolved 
    | throwError s!"Representation map '{liftTResolved}' not found."
  let some _ := env.find? domResolved 
    | throwError s!"Domain '{domResolved}' not found."
  let some _ := env.find? codResolved 
    | throwError s!"Codomain '{codResolved}' not found."

  -- 2. Method Mode Deny-List Enforcement (all candidate declarations in environment)
  let candidateDecls := getCandidateDecls env
  let allDecls := if candidateDecls.contains bPropResolved then candidateDecls else [domResolved, codResolved, liftTResolved, bPropResolved, lClaimResolved] ++ candidateDecls
  checkDirectProhibited env allDecls prohibited

  -- 3. Representation Axiom Audit across ALL candidate declarations (fail-closed, zero sorryAx, zero custom axioms)
  let allowedRepAxioms : List Name := [`propext, `Classical.choice, `Quot.sound]
  for cName in allDecls do
    let axioms ← Lean.collectAxioms cName
    for ax in axioms do
      if !allowedRepAxioms.contains ax then
        throwError s!"FORBIDDEN_REPRESENTATION_AXIOM: Declaration '{cName}' transitively depends on axiom '{ax}'."

  -- 4. Identity Guard (AND semantics: LiftDom = LiftCod AND liftT = id)
  let domEqCod ← isDefEq (mkConst domResolved) (mkConst codResolved)
  if domEqCod then
    let idFn ← mkAppOptM ``id #[some (mkConst domResolved)]
    let isId ← isDefEq (mkConst liftTResolved) idFn
    if isId then
      throwError "IDENTITY_GUARD: Representation map is definitionally the identity function on identical domains."

  -- 5. Target Linkage & Sequential Dependent Binder Comparison
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
