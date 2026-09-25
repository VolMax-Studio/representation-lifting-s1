import Lean

open Lean

/-!
# Verifier.lean
Standalone Compiled Adjudicator Executable for representation-lifting-s1 (v0.10).

Architecture:
1. Compiled native binary (`.lake/build/bin/verifier`).
2. Zero Lean syntax elaboration after importing candidate code.
3. Loads candidate .olean files directly into `Environment` via `Lean.importModules`.
4. Directly invokes Lean 4 `MetaM` verification algorithms.
5. Emits structured JSON verification receipts and definitive process exit codes (0 for PASS, 1 for FAIL).
6. Immune to syntax hijacking (`elab_rules`, `macro_rules`, notation, attribute overrides).
-/

def mkJson (verdict subcmd candMod : String) (checks : List (String × Bool)) : String :=
  let checkLines := checks.map (fun p => "    \"" ++ p.1 ++ "\": " ++ (if p.2 then "true" else "false"))
  let checksObj := "{\n" ++ (String.intercalate ",\n" checkLines) ++ "\n  }"
  "{\n" ++
  "  \"verdict\": \"" ++ verdict ++ "\",\n" ++
  "  \"subcommand\": \"" ++ subcmd ++ "\",\n" ++
  "  \"candidate_module\": \"" ++ candMod ++ "\",\n" ++
  "  \"checks\": " ++ checksObj ++ "\n" ++
  "}"

def mkErrJson (subcmd candMod err : String) : String :=
  "{\n" ++
  "  \"verdict\": \"FAIL\",\n" ++
  "  \"subcommand\": \"" ++ subcmd ++ "\",\n" ++
  "  \"candidate_module\": \"" ++ candMod ++ "\",\n" ++
  "  \"error\": \"" ++ (err.replace "\"" "\\\"" |>.replace "\n" "\\n") ++ "\"\n" ++
  "}"

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
            throwError m!"FORBIDDEN_METHOD_MODE_CONSTANT: Declaration '{d}' references prohibited constant '{c}'."

def resolveInModule (env : Environment) (modIdx : ModuleIdx) (targetShortName : String) : MetaM Name := do
  let consts := env.header.moduleData[modIdx.toNat]!.constants
  for c in consts do
    if match c.name with | .str _ s => s == targetShortName | _ => false then
      return c.name
  throwError m!"Declaration '{targetShortName}' not found in module."

def hasConstRef (e : Expr) (targetConst : Name) : Bool :=
  e.foldConsts false (fun name acc => acc || (name == targetConst))

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

def runVerifyTarget (candModName frozenTargetName : Name) (executorShortName : String) (prohibited : List Name) : MetaM String := do
  let env ← getEnv
  
  -- 1. Locate Candidate Module
  let some candIdx := env.getModuleIdx? candModName
    | throwError m!"Candidate module '{candModName}' not found in environment."
  
  let candidateConsts := env.header.moduleData[candIdx.toNat]!.constants
  let candidateDecls := candidateConsts.map (·.name) |>.toList
  
  -- 2. Method Mode Deny-List Audit across ALL candidate declarations
  checkDirectProhibited env candidateDecls prohibited

  -- 3. Resolve target and executor declarations
  let some targetDecl := env.find? frozenTargetName
    | throwError m!"Target declaration '{frozenTargetName}' not found in environment."
  
  let executorResolved ← resolveInModule env candIdx executorShortName
  let some executorDecl := env.find? executorResolved
    | throwError m!"Executor declaration '{executorResolved}' not found in environment."

  -- 4. Definitional equality of full types
  let targetType := targetDecl.type
  let executorType := executorDecl.type
  
  if !(← isDefEq targetType executorType) then
    throwError m!"TYPE_MISMATCH: Executor theorem type does not match frozen target type:\n  Expected: {targetType}\n  Received: {executorType}"

  -- 5. Mechanical Target Verification & Kernel Replay via addDecl
  let checkName := `VerifierTrustCore.d_check
  let levels := targetDecl.levelParams.map Level.param
  let proof := mkConst executorResolved levels
  let decl := Declaration.thmDecl {
    name := checkName
    levelParams := targetDecl.levelParams
    type := targetDecl.type
    value := proof
  }
  addDecl decl

  -- 6. Fail-Closed Axiom Audit on kernel-checked declaration
  let axioms ← Lean.collectAxioms checkName
  let allowedAxioms : List Name := [`propext, `Classical.choice, `Quot.sound]
  
  for ax in axioms do
    if !allowedAxioms.contains ax then
      throwError m!"FORBIDDEN_AXIOM: Proof transitively relies on non-standard axiom '{ax}'."

  let checks := [
    ("module_found", true),
    ("method_mode", true),
    ("type_match", true),
    ("kernel_checked", true),
    ("axioms", true)
  ]
  return mkJson "PASS" "target" (toString candModName) checks

def runVerifyLifted (candModName frozenSpecModName frozenTargetName : Name) (prohibited : List Name) : MetaM String := do
  let env ← getEnv
  
  -- 1. Locate Modules
  let some candIdx := env.getModuleIdx? candModName
    | throwError m!"Candidate module '{candModName}' not found in environment."
  let some specIdx := env.getModuleIdx? frozenSpecModName
    | throwError m!"Frozen specification module '{frozenSpecModName}' not found in environment."
  
  let candidateConsts := env.header.moduleData[candIdx.toNat]!.constants
  let candidateDecls := candidateConsts.map (·.name) |>.toList
  
  -- 2. Method Mode Deny-List Audit across ALL candidate declarations
  checkDirectProhibited env candidateDecls prohibited

  -- 3. Resolve Target, Specification, and Candidate declarations
  let some targetDecl := env.find? frozenTargetName
    | throwError m!"Target declaration '{frozenTargetName}' not found in environment."
  
  let bPropResolved ← resolveInModule env specIdx "BridgeProp"
  let lClaimResolved ← resolveInModule env specIdx "LiftedClaim"
  
  let bridgeResolved ← resolveInModule env candIdx "preservation_bridge"
  let liftedResolved ← resolveInModule env candIdx "lifted_theorem"
  
  let some bridgeDecl := env.find? bridgeResolved
    | throwError m!"Preservation bridge '{bridgeResolved}' not found."
  let some liftedDecl := env.find? liftedResolved
    | throwError m!"Lifted theorem '{liftedResolved}' not found."

  -- 4. Kernel Axiom Audit on Candidate declarations
  let allowedAxioms : List Name := [`propext, `Classical.choice, `Quot.sound]
  for d in [bridgeResolved, liftedResolved] do
    let axioms ← Lean.collectAxioms d
    for ax in axioms do
      if !allowedAxioms.contains ax then
        throwError m!"FORBIDDEN_AXIOM: Declaration '{d}' relies on non-standard axiom '{ax}'."

  -- 5. Type Equivalence
  let bridgePropType := mkConst bPropResolved
  let liftedClaimType := mkConst lClaimResolved
  
  if !(← isDefEq bridgeDecl.type bridgePropType) then
    throwError "TYPE_MISMATCH: preservation_bridge type does not match BridgeProp."
  if !(← isDefEq liftedDecl.type liftedClaimType) then
    throwError "TYPE_MISMATCH: lifted_theorem type does not match LiftedClaim."

  -- 6. Transitive Module-Local Non-Circularity Audit
  let liftedDeps ← collectTransitiveCandidateDeps env candIdx liftedResolved bridgeResolved {}
  if liftedDeps.contains bridgeResolved then
    throwError m!"CIRCULAR_LIFT_DEPENDENCY: lifted_theorem '{liftedResolved}' transitively depends on preservation_bridge '{bridgeResolved}'."

  -- 7. Mechanical Target Synthesis & Kernel Axiom Verification
  forallTelescope targetDecl.type fun xs targetConcl => do
    let bridgeApp := mkAppN (mkConst bridgeResolved) xs
    let liftedApp := mkAppN (mkConst liftedResolved) xs

    let bridgeType ← inferType bridgeApp
    let bridgeTypeWhnf ← whnf bridgeType
    let some (lhs, rhs) := bridgeTypeWhnf.iff?
      | throwError m!"SYNTHESIS_FAILED: Bridge property conclusion under telescope is not an equivalence (↔):\n  {bridgeTypeWhnf}"

    let isLhsTarget ← isDefEq lhs targetConcl
    let isRhsTarget ← isDefEq rhs targetConcl
    if !isLhsTarget && !isRhsTarget then
      throwError m!"SYNTHESIS_FAILED: Neither side of bridge equivalence matches target conclusion:\n  Target: {targetConcl}\n  LHS: {lhs}\n  RHS: {rhs}"

    let iffFn := if isLhsTarget then ``Iff.mpr else ``Iff.mp
    let conclProof ← mkAppM iffFn #[bridgeApp, liftedApp]
    let fullProof ← mkLambdaFVars xs conclProof
    let fullProofType ← inferType fullProof

    if !(← isDefEq fullProofType targetDecl.type) then
      throwError m!"SYNTHESIS_FAILED: Synthesized proof type does not match target type:\n  Expected: {targetDecl.type}\n  Received: {fullProofType}"

    let synthName := `VerifierTrustCore.synthesized_target
    let decl := Declaration.thmDecl {
      name := synthName
      levelParams := []
      type := targetDecl.type
      value := fullProof
    }

    addDecl decl

    let sAxioms ← Lean.collectAxioms synthName
    for ax in sAxioms do
      if !allowedAxioms.contains ax then
        throwError m!"FORBIDDEN_AXIOM: Synthesized target relies on non-standard axiom '{ax}'."

  let checks := [
    ("modules_found", true),
    ("method_mode", true),
    ("bridge_type", true),
    ("lifted_type", true),
    ("non_circular", true),
    ("target_synthesis", true),
    ("axioms", true)
  ]
  return mkJson "PASS" "lifted" (toString candModName) checks

def runCheckBridge (candModName frozenTargetName : Name) (prohibited : List Name) : MetaM String := do
  let env ← getEnv
  
  -- 1. Locate Candidate Module
  let some candIdx := env.getModuleIdx? candModName
    | throwError m!"Candidate module '{candModName}' not found in environment."
  
  let candidateConsts := env.header.moduleData[candIdx.toNat]!.constants
  let candidateDecls := candidateConsts.map (·.name) |>.toList
  
  -- 2. Method Mode Deny-List Audit across ALL candidate declarations
  checkDirectProhibited env candidateDecls prohibited

  -- 3. Resolve Structural Declarations inside Candidate Module
  let some targetDecl := env.find? frozenTargetName 
    | throwError m!"Target declaration '{frozenTargetName}' not found in environment."
  
  let bPropResolved ← resolveInModule env candIdx "BridgeProp"
  let lClaimResolved ← resolveInModule env candIdx "LiftedClaim"
  let liftTResolved ← resolveInModule env candIdx "liftT"
  let domResolved ← resolveInModule env candIdx "LiftDom"
  let codResolved ← resolveInModule env candIdx "LiftCod"

  let some (.defnInfo bridgePropVal) := env.find? bPropResolved 
    | throwError m!"Declaration '{bPropResolved}' is not a definition."
  let some (.defnInfo liftedClaimVal) := env.find? lClaimResolved 
    | throwError m!"Declaration '{lClaimResolved}' is not a definition."
  let some liftTDecl := env.find? liftTResolved 
    | throwError m!"Declaration '{liftTResolved}' not found."
  let some _ := env.find? domResolved 
    | throwError m!"Declaration '{domResolved}' not found."
  let some _ := env.find? codResolved 
    | throwError m!"Declaration '{codResolved}' not found."

  -- 4. Pure Representation Axiom Audit across ALL Candidate Declarations (zero sorryAx)
  let allowedAxioms : List Name := [`propext, `Classical.choice, `Quot.sound]
  for d in candidateDecls do
    let axioms ← Lean.collectAxioms d
    for ax in axioms do
      if !allowedAxioms.contains ax then
        throwError m!"FORBIDDEN_AXIOM: Specification declaration '{d}' relies on non-standard axiom '{ax}'."

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
        throwError m!"BINDER_COUNT_MISMATCH: Target has {targetVars.size} binders, bridge prop has {bridgeVars.size} binders."

      -- Check binder types sequentially with dependent substitution
      for i in [:targetVars.size] do
        let tVar := targetVars[i]!
        let bVar := bridgeVars[i]!
        let tType ← inferType tVar
        let bType ← inferType bVar
        let bTypeSubst := bType.replaceFVars (bridgeVars.extract 0 i) (targetVars.extract 0 i)
        if !(← isDefEq tType bTypeSubst) then
          throwError m!"BINDER_TYPE_MISMATCH: Binder {i} type mismatch: target expects {tType}, bridge has {bTypeSubst}"

      -- Substitute bridge free variables with target free variables in conclusion
      let bridgeConclSubst := bridgeConcl.replaceFVars bridgeVars targetVars

      -- Check that conclusion is an Iff (↔)
      let some (lhs, rhs) := bridgeConclSubst.iff? 
        | throwError m!"NON_EQUIVALENCE_BRIDGE: Bridge conclusion is not an equivalence (↔): {bridgeConclSubst}"

      -- Tautology check
      if lhs == rhs then
        throwError m!"TAUTOLOGICAL_BRIDGE: Bridge equivalence is syntactically tautological ({lhs} ↔ {rhs})."

      -- Match one side against target conclusion
      let lhsMatchesTarget ← isDefEq lhs targetConcl
      let rhsMatchesTarget ← isDefEq rhs targetConcl

      if !lhsMatchesTarget && !rhsMatchesTarget then
        throwError m!"UNLINKED_TARGET: Neither side of bridge matches target conclusion:\n  Target: {targetConcl}\n  LHS: {lhs}\n  RHS: {rhs}"

      let liftedSide := if lhsMatchesTarget then rhs else lhs
      if !hasConstRef liftedSide liftTResolved then
        throwError m!"UNLIFTED_BRIDGE: Lifted side does not contain constant '{liftTResolved}':\n  {liftedSide}"

      -- Verify that liftedSide matches LiftedClaim peeled conclusion
      forallTelescope liftedClaimVal.value fun claimVars claimConcl => do
        if claimVars.size != targetVars.size then
          throwError m!"CLAIM_BINDER_COUNT_MISMATCH: LiftedClaim has {claimVars.size} binders, expected {targetVars.size}."
        let claimConclSubst := claimConcl.replaceFVars claimVars targetVars
        if !(← isDefEq liftedSide claimConclSubst) then
          throwError m!"UNLINKED_LIFTED_CLAIM: Lifted side of bridge does not match LiftedClaim:\n  Bridge lifted side: {liftedSide}\n  LiftedClaim: {claimConclSubst}"

  let checks := [
    ("module_found", true),
    ("method_mode", true),
    ("declarations_resolved", true),
    ("representation_axioms", true),
    ("identity_guard", true),
    ("binder_matching", true),
    ("equivalence_conclusion", true),
    ("non_tautological", true),
    ("target_linked", true),
    ("lifted_claim_linked", true)
  ]
  return mkJson "PASS" "bridge" (toString candModName) checks

end VerifierTrustCore

def parseProhibited (s : String) : List Lean.Name :=
  let cleaned := s.replace "[" "" |>.replace "]" "" |>.replace "`" ""
  let parts := cleaned.splitOn ","
  parts.filterMap (fun p =>
    let p := p.trimAscii.toString
    if p.isEmpty then none else some p.toName
  )

def runMetaMAction (env : Lean.Environment) (act : Lean.MetaM String) : IO (Except String String) := do
  let coreCtx : Lean.Core.Context := { fileName := "<verifier>", fileMap := default }
  let coreState : Lean.Core.State := { env := env }
  try
    let (res, _) ← (act.run' {} {}).toIO coreCtx coreState
    return .ok res
  catch e =>
    return .error e.toString

def printUsage : IO Unit := do
  IO.eprintln "Usage: verifier <subcommand> [args...]"
  IO.eprintln "Subcommands:"
  IO.eprintln "  target <candidate_mod> <frozen_target_name> <executor_theorem_name> [prohibited_list]"
  IO.eprintln "  lifted <candidate_mod> <frozen_spec_mod> <frozen_target_name> [prohibited_list]"
  IO.eprintln "  bridge <candidate_mod> <frozen_target_name> [prohibited_list]"

def main (args : List String) : IO UInt32 := do
  match args with
  | "target" :: candModStr :: frozenTargetStr :: execNameStr :: rest => do
    let prohibited := match rest with | p :: _ => parseProhibited p | [] => []
    initSearchPath (← findSysroot)
    let candMod := candModStr.toName
    let frozenTarget := frozenTargetStr.toName
    let env ← importModules #[{ module := `TrustedTargetModule }, { module := candMod }] {}
    match ← runMetaMAction env (VerifierTrustCore.runVerifyTarget candMod frozenTarget execNameStr prohibited) with
    | .ok receipt =>
      IO.println receipt
      IO.println s!"VERIFICATION_SUCCESS: '{execNameStr}' matches '{frozenTarget}' definitionally."
      return 0
    | .error err =>
      let errReceipt := mkErrJson "target" (toString candMod) err
      IO.eprintln errReceipt
      IO.eprintln s!"VERIFICATION_FAILED: {err}"
      return 1

  | "lifted" :: candModStr :: frozenSpecModStr :: frozenTargetStr :: rest => do
    let prohibited := match rest with | p :: _ => parseProhibited p | [] => []
    initSearchPath (← findSysroot)
    let candMod := candModStr.toName
    let specMod := frozenSpecModStr.toName
    let frozenTarget := frozenTargetStr.toName
    let env ← importModules #[{ module := `TrustedTargetModule }, { module := specMod }, { module := candMod }] {}
    match ← runMetaMAction env (VerifierTrustCore.runVerifyLifted candMod specMod frozenTarget prohibited) with
    | .ok receipt =>
      IO.println receipt
      IO.println "VERIFY_LIFTED_SENTINEL_OK"
      return 0
    | .error err =>
      let errReceipt := mkErrJson "lifted" (toString candMod) err
      IO.eprintln errReceipt
      IO.eprintln s!"VERIFY_LIFTED_FAILED: {err}"
      return 1

  | "bridge" :: candModStr :: frozenTargetStr :: rest => do
    let prohibited := match rest with | p :: _ => parseProhibited p | [] => []
    initSearchPath (← findSysroot)
    let candMod := candModStr.toName
    let frozenTarget := frozenTargetStr.toName
    let env ← importModules #[{ module := `TrustedTargetModule }, { module := candMod }] {}
    match ← runMetaMAction env (VerifierTrustCore.runCheckBridge candMod frozenTarget prohibited) with
    | .ok receipt =>
      IO.println receipt
      IO.println "CHECK_BRIDGE_SENTINEL_OK"
      return 0
    | .error err =>
      let errReceipt := mkErrJson "bridge" (toString candMod) err
      IO.eprintln errReceipt
      IO.eprintln s!"VERIFICATION_FAILED: {err}"
      return 1

  | _ => do
    printUsage
    return 2
