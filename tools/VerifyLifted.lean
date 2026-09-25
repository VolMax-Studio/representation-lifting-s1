import Lean

/-!
tools/VerifyLifted.lean
Pure Lean 4 meta-checker for Structural Lifted Proof (Role L) Verification:
1. Lean-Native Candidate Declaration Enumeration:
   Inspects environment for all declarations in `CandidateExecutor` namespace.
2. Verifies existence of:
   - `frozen_target`
   - `BridgeProp` (frozen specification property linking target and LiftedClaim)
   - `LiftedClaim` (frozen closed lifted proposition)
   - `preservation_bridge` (proved bridge theorem)
   - `lifted_theorem` (proved theorem on lifted representation)
3. Type Equivalence Audits:
   - `type(preservation_bridge) ≡_def BridgeProp`
   - `type(lifted_theorem) ≡_def LiftedClaim`
4. Fail-Closed Axiom Audits (zero sorryAx permitted):
   - Transitive axioms of `preservation_bridge` ⊆ {propext, Classical.choice, Quot.sound}
   - Transitive axioms of `lifted_theorem` ⊆ {propext, Classical.choice, Quot.sound}
5. Transitive Module-Local Non-Circularity Audit:
   - Computes transitive local dependency closure of `lifted_theorem` using `NameSet`.
   - Asserts: `preservation_bridge ∉ Deps*(lifted_theorem)`.
   - Traverses any helper definitions/theorems authored in `CandidateExecutor`.
6. Method Mode Deny-List Audit:
   - Recursively inspects direct constant references in all candidate-authored declarations
   - against prohibited library constants (exact and prefix match).
7. Mechanical Trusted Target Synthesis:
   - Analyzes BridgeProp equivalence orientation under target telescope.
   - Mechanically synthesizes `synthesized_target := fun xs => (preservation_bridge xs).mpr/.mp (lifted_theorem xs)`.
   - Asserts `type(synthesized_target) ≡_def type(frozen_target)`.
   - Adds `synthesized_target` to environment and executes strict kernel axiom audit.
8. Prints strict sentinel: `VERIFY_LIFTED_SENTINEL_OK`.
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

partial def collectTransitiveLocalDeps (env : Environment) (name : Name) (bridgeName : Name) (visited : NameSet) : MetaM NameSet := do
  if visited.contains name then return visited
  let mut visited := visited.insert name
  if let some decl := env.find? name then
    if let some val := getDeclValue? decl then
      let consts := val.foldConsts [] (fun c acc => if acc.contains c then acc else c :: acc)
      for c in consts do
        if c == bridgeName then
          visited := visited.insert bridgeName
        else if isCandidateDecl c then
          visited ← collectTransitiveLocalDeps env c bridgeName visited
  return visited

def checkNonCircularityTransitive (env : Environment) (liftedThmName bridgeThmName : Name) : MetaM Unit := do
  let deps ← collectTransitiveLocalDeps env liftedThmName bridgeThmName {}
  if deps.contains bridgeThmName then
    throwError s!"CIRCULAR_LIFT_DEPENDENCY: '{liftedThmName}' transitively references '{bridgeThmName}' in dependency closure."

def runVerifyLifted (frozenTargetName bridgePropName liftedClaimName bridgeThmName liftedThmName : Name) (prohibited : List Name) : MetaM Unit := do
  let env ← getEnv

  -- 1. Existence checks & Name resolution
  let some targetDecl := env.find? frozenTargetName
    | throwError s!"Target declaration '{frozenTargetName}' not found in environment."
  let bPropResolved ← resolveCandidateName env bridgePropName
  let lClaimResolved ← resolveCandidateName env liftedClaimName
  let bThmResolved ← resolveCandidateName env bridgeThmName
  let lThmResolved ← resolveCandidateName env liftedThmName

  let some bridgeThmDecl := env.find? bThmResolved
    | throwError s!"Bridge proof declaration '{bThmResolved}' not found in environment."
  let some liftedThmDecl := env.find? lThmResolved
    | throwError s!"Lifted proof declaration '{lThmResolved}' not found in environment."

  -- 2. Method Mode Deny-List Audit (all candidate declarations)
  let candidateDecls := getCandidateDecls env
  let allDecls := if candidateDecls.contains bThmResolved then candidateDecls else bThmResolved :: lThmResolved :: candidateDecls
  checkDirectProhibited env allDecls prohibited

  -- 3. Transitive Non-Circularity Check
  checkNonCircularityTransitive env lThmResolved bThmResolved

  -- 4. Definitional match of types
  let bridgeThmType := bridgeThmDecl.type
  let bridgePropType := mkConst bPropResolved
  if !(← isDefEq bridgeThmType bridgePropType) then
    throwError s!"BRIDGE_PROP_MISMATCH: '{bThmResolved}' does not prove '{bPropResolved}':\n  Expected: {bridgePropType}\n  Received: {bridgeThmType}"

  let liftedThmType := liftedThmDecl.type
  let liftedClaimType := mkConst lClaimResolved
  if !(← isDefEq liftedThmType liftedClaimType) then
    throwError s!"LIFTED_CLAIM_MISMATCH: '{lThmResolved}' does not prove '{lClaimResolved}':\n  Expected: {liftedClaimType}\n  Received: {liftedThmType}"

  -- 5. Strict Axiom Audit on author components (zero sorryAx, zero non-standard axioms)
  let allowedAxioms : List Name := [`propext, `Classical.choice, `Quot.sound]
  
  let bridgeAxioms ← Lean.collectAxioms bThmResolved
  for ax in bridgeAxioms do
    if !allowedAxioms.contains ax then
      throwError s!"FORBIDDEN_AXIOM: Bridge proof '{bThmResolved}' transitively relies on axiom '{ax}'."

  let liftedAxioms ← Lean.collectAxioms lThmResolved
  for ax in liftedAxioms do
    if !allowedAxioms.contains ax then
      throwError s!"FORBIDDEN_AXIOM: Lifted proof '{lThmResolved}' transitively relies on axiom '{ax}'."

  -- 6. Actual Mechanical Synthesis of Original Executor Theorem
  forallTelescope targetDecl.type fun xs targetConcl => do
    let bridgeConst := mkConst bThmResolved (bridgeThmDecl.levelParams.map Level.param)
    let liftedConst := mkConst lThmResolved (liftedThmDecl.levelParams.map Level.param)
    let bridgeApp := mkAppN bridgeConst xs
    let liftedApp := mkAppN liftedConst xs
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

    let synthName := `CandidateExecutor.synthesized_target
    let decl := Declaration.thmDecl {
      name := synthName
      levelParams := targetDecl.levelParams
      type := targetDecl.type
      value := fullProof
    }
    addDecl decl

    let synthAxioms ← Lean.collectAxioms synthName
    for ax in synthAxioms do
      if !allowedAxioms.contains ax then
        throwError s!"FORBIDDEN_AXIOM: Synthesized target theorem relies on non-standard axiom '{ax}'."

  IO.println s!"VERIFY_LIFTED_SENTINEL_OK"
