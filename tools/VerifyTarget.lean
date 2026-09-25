import Lean

/-!
tools/VerifyTarget.lean
Pure Lean 4 meta-checker for Exact Target Match, Axiom Audit, and Method Mode Deny-List:
1. Strict Module Provenance:
   Candidate declarations are identified strictly by module index (`idx(candModName)`).
   Zero reliance on name prefixes, namespaces, `_root_`, `_aux`, or allowlists.
2. Method Mode Deny-List Enforcement:
   Recursively inspects direct constant references in all declarations authored in candidate module.
3. Type Equivalence:
   asserts type(executor_theorem) ≡_def type(frozen_target).
4. Strict Kernel Axiom Audit:
   Asserts A_observed ⊆ {propext, Classical.choice, Quot.sound}.
5. Sentinel: VERIFICATION_SUCCESS.
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

def resolveInCandidateModule (env : Environment) (candIdx : ModuleIdx) (targetShortName : String) : MetaM Name := do
  let consts := env.header.moduleData[candIdx.toNat]!.constants
  for c in consts do
    if match c.name with | .str _ s => s == targetShortName | _ => false then
      return c.name
  throwError s!"Declaration '{targetShortName}' not found in candidate module."

def runVerifyTarget (candModName frozenTargetName executorShortName : Name) (prohibited : List Name) : MetaM Unit := do
  let env ← getEnv
  
  -- 1. Locate Candidate Module
  let some candIdx := env.getModuleIdx? candModName
    | throwError s!"Candidate module '{candModName}' not found in environment."
  
  let candidateConsts := env.header.moduleData[candIdx.toNat]!.constants
  let candidateDecls := candidateConsts.map (·.name) |>.toList
  
  -- 2. Method Mode Deny-List Audit across ALL declarations authored in candidate module
  checkDirectProhibited env candidateDecls prohibited

  -- 3. Resolve target and executor declarations
  let some targetDecl := env.find? frozenTargetName
    | throwError s!"Target declaration '{frozenTargetName}' not found in environment."
  
  let executorResolved ← resolveInCandidateModule env candIdx (executorShortName.getString!)
  let some executorDecl := env.find? executorResolved
    | throwError s!"Executor declaration '{executorResolved}' not found in environment."

  -- 4. Definitional equality of full types
  let targetType := targetDecl.type
  let executorType := executorDecl.type
  
  if !(← isDefEq targetType executorType) then
    throwError s!"TYPE_MISMATCH: Executor theorem type does not match frozen target type:\n  Expected: {targetType}\n  Received: {executorType}"

  -- 5. Fail-Closed Axiom Audit
  let axioms ← Lean.collectAxioms executorResolved
  let allowedAxioms : List Name := [`propext, `Classical.choice, `Quot.sound]
  
  for ax in axioms do
    if !allowedAxioms.contains ax then
      throwError s!"FORBIDDEN_AXIOM: Proof transitively relies on non-standard axiom '{ax}'."

  IO.println s!"VERIFICATION_SUCCESS: '{executorResolved}' matches '{frozenTargetName}' definitionally with certified kernel axioms: {axioms.toList}"

end VerifierTrustCore
