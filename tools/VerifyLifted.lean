import Lean

/-!
tools/VerifyLifted.lean
Pure Lean 4 meta-checker for Structural Lifted Proof (Role L) Verification:
1. Strict Module Provenance:
   Candidate declarations are identified strictly by module index (`idx(candModName)`).
   Zero reliance on name prefixes, namespaces, `_root_`, `_aux`, or allowlists.
2. Method Mode Deny-List Audit:
   Inspects all declarations authored in candidate module against prohibited constants.
3. Axiom Audits:
   Transitive axioms of `preservation_bridge` and `lifted_theorem` ⊆ {propext, Classical.choice, Quot.sound}.
4. Type Equivalence Audits:
   - `type(preservation_bridge) ≡_def BridgeProp`
   - `type(lifted_theorem) ≡_def LiftedClaim`
5. Transitive Candidate-Local Non-Circularity Audit:
   Traverses dependencies strictly within candidate module.
   Asserts: `preservation_bridge ∉ Deps*(lifted_theorem)`.
6. Mechanical Target Synthesis & Kernel Axiom Verification:
   Synthesizes `synthesized_target := fun xs => (preservation_bridge xs).mpr/.mp (lifted_theorem xs)`.
   Asserts `type(synthesized_target) ≡_def type(frozen_target)`.
   Adds theorem to environment and performs kernel axiom audit.
7. Sentinel: `VERIFY_LIFTED_SENTINEL_OK`.
Part of representation-lifting-s1 experimental protocol (v0.9).
-/

namespace VerifierTrustCore

set_option linter.unusedVariables false

open Lean Meta

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
            throwError s!"FORBIDDEN_METHOD_MODE_CONSTANT: Declaration '{d}' references prohibited constant '{c}'."

def resolveInModule (env : Environment) (modIdx : ModuleIdx) (targetShortName : String) : MetaM Name := do
  let consts := env.header.moduleData[modIdx.toNat]!.constants
  for c in consts do
    if match c.name with | .str _ s => s == targetShortName | _ => false then
      return c.name
  throwError s!"Declaration '{targetShortName}' not found in module."

partial def collectTransitiveCandidateDeps (env : Environment) (candIdx : ModuleIdx) (name : Name) (bridgeName : Name) (visited : NameSet) : MetaM NameSet := do
  if visited.contains name then return visited
  let mut visited := visited.insert name
  if let some decl := env.find? name then
    if let some val := getDeclValue? decl then
      let consts := val.foldConsts [] (fun c acc => if acc.contains c then acc else c :: acc)
      for c in consts do
        if c == bridgeName then
          visited := visited.insert bridgeName
        else if env.getModuleIdxFor? c == some candIdx then
          visited ← collectTransitiveCandidateDeps env candIdx c bridgeName visited
  return visited

def runVerifyLifted (candModName frozenSpecModName frozenTargetName : Name) (prohibited : List Name) : MetaM Unit := do
  let env ← getEnv
  
  -- 1. Locate Modules
  let some candIdx := env.getModuleIdx? candModName
    | throwError s!"Candidate module '{candModName}' not found in environment."
  let some specIdx := env.getModuleIdx? frozenSpecModName
    | throwError s!"Frozen specification module '{frozenSpecModName}' not found in environment."
  
  let candidateConsts := env.header.moduleData[candIdx.toNat]!.constants
  let candidateDecls := candidateConsts.map (·.name) |>.toList
  
  -- 2. Method Mode Deny-List Audit across ALL candidate declarations
  checkDirectProhibited env candidateDecls prohibited

  -- 3. Resolve Target, Specification, and Candidate declarations
  let some targetDecl := env.find? frozenTargetName
    | throwError s!"Target declaration '{frozenTargetName}' not found in environment."
  
  let bPropResolved ← resolveInModule env specIdx "BridgeProp"
  let lClaimResolved ← resolveInModule env specIdx "LiftedClaim"
  
  let bridgeResolved ← resolveInModule env candIdx "preservation_bridge"
  let liftedResolved ← resolveInModule env candIdx "lifted_theorem"
  
  let some bridgeDecl := env.find? bridgeResolved
    | throwError s!"Preservation bridge '{bridgeResolved}' not found."
  let some liftedDecl := env.find? liftedResolved
    | throwError s!"Lifted theorem '{liftedResolved}' not found."

  -- 4. Kernel Axiom Audit on Candidate declarations
  let allowedAxioms : List Name := [`propext, `Classical.choice, `Quot.sound]
  for d in [bridgeResolved, liftedResolved] do
    let axioms ← Lean.collectAxioms d
    for ax in axioms do
      if !allowedAxioms.contains ax then
        throwError s!"FORBIDDEN_AXIOM: Declaration '{d}' relies on non-standard axiom '{ax}'."

  -- 5. Type Equivalence
  let bridgePropType := mkConst bPropResolved
  let liftedClaimType := mkConst lClaimResolved
  
  if !(← isDefEq bridgeDecl.type bridgePropType) then
    throwError s!"TYPE_MISMATCH: preservation_bridge type does not match BridgeProp."
  if !(← isDefEq liftedDecl.type liftedClaimType) then
    throwError s!"TYPE_MISMATCH: lifted_theorem type does not match LiftedClaim."

  -- 6. Transitive Module-Local Non-Circularity Audit
  let liftedDeps ← collectTransitiveCandidateDeps env candIdx liftedResolved bridgeResolved {}
  if liftedDeps.contains bridgeResolved then
    throwError s!"CIRCULAR_LIFT_DEPENDENCY: lifted_theorem '{liftedResolved}' transitively depends on preservation_bridge '{bridgeResolved}'."

  -- 7. Mechanical Target Synthesis & Kernel Axiom Verification
  forallTelescope targetDecl.type fun xs targetConcl => do
    let bridgeApp := mkAppN (mkConst bridgeResolved) xs
    let liftedApp := mkAppN (mkConst liftedResolved) xs

    let bridgeType ← inferType bridgeApp
    let bridgeTypeWhnf ← whnf bridgeType
    let some (lhs, rhs) := bridgeTypeWhnf.iff?
      | throwError s!"SYNTHESIS_FAILED: Bridge property conclusion under telescope is not an equivalence (↔):\n  {bridgeTypeWhnf}"

    let isLhsTarget ← isDefEq lhs targetConcl
    let isRhsTarget ← isDefEq rhs targetConcl
    if !isLhsTarget && !isRhsTarget then
      throwError s!"SYNTHESIS_FAILED: Neither side of bridge equivalence matches target conclusion:\n  Target: {targetConcl}\n  LHS: {lhs}\n  RHS: {rhs}"

    let iffFn := if isLhsTarget then ``Iff.mpr else ``Iff.mp
    let conclProof ← mkAppM iffFn #[bridgeApp, liftedApp]
    let fullProof ← mkLambdaFVars xs conclProof
    let fullProofType ← inferType fullProof

    if !(← isDefEq fullProofType targetDecl.type) then
      throwError s!"SYNTHESIS_FAILED: Synthesized proof type does not match target type:\n  Expected: {targetDecl.type}\n  Received: {fullProofType}"

    let synthName := `VerifierTrustCore.synthesized_target
    let decl := Declaration.thmDecl {
      name := synthName
      levelParams := []
      type := targetDecl.type
      value := fullProof
    }

    addDecl decl

    let synthAxioms ← Lean.collectAxioms synthName
    for ax in synthAxioms do
      if !allowedAxioms.contains ax then
        throwError s!"FORBIDDEN_AXIOM: Synthesized target relies on non-standard axiom '{ax}'."

  IO.println "VERIFY_LIFTED_SENTINEL_OK"

end VerifierTrustCore
