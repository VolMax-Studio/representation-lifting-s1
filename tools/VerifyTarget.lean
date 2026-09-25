import Lean

/-!
tools/VerifyTarget.lean
Pure Lean 4 meta-checker for Exact Target Match, Axiom Audit, and Method Mode Deny-List:
1. Module Provenance-Based Candidate Declaration Enumeration:
   Inspects environment for all declarations authored in the current execution module
   (env.getModuleIdxFor? name = none), excluding trusted verifier/target definitions.
   Captures all declarations regardless of namespace, `_root_`, `end` escapes, private, or Unicode names.
2. Verifies that `frozen_target` and `executor_theorem` are declared.
3. Uses `isDefEq` on their full types:
   asserts type(executor_theorem) ≡_def type(frozen_target).
4. Strict Kernel Axiom Audit:
   Asserts A_observed ⊆ {propext, Classical.choice, Quot.sound}.
   Rejects sorryAx, custom axioms, or unproved constants.
5. Method Mode Deny-List Enforcement:
   Recursively inspects direct constant references in all candidate declarations
   against prohibited library constants (exact and prefix match).
6. Fail-closed: Any compilation or meta error terminates with non-zero exit code.
Part of representation-lifting-s1 experimental protocol (v0.8).
-/

namespace VerifierTrustCore

set_option linter.unusedVariables false

open Lean Meta

def getDeclValue? (decl : ConstantInfo) : Option Expr :=
  match decl with
  | .thmInfo v => some v.value
  | .defnInfo v => some v.value
  | _ => none

def isTrusted (trustedNames : List Name) (n : Name) : Bool :=
  (`VerifierTrustCore).isPrefixOf n ||
  trustedNames.contains n ||
  (`_eval).isPrefixOf n ||
  (`_unsafe_rec).isPrefixOf n ||
  n == `_eval ||
  match n with
  | .str _ s => s.startsWith "_aux" || s.startsWith "_eval"
  | _ => false

def getCandidateDecls (env : Environment) (trustedNames : List Name) : List Name :=
  env.constants.fold (fun acc name _ =>
    if env.getModuleIdxFor? name == none && !isTrusted trustedNames name then
      name :: acc
    else
      acc
  ) []

def resolveCandidateName (env : Environment) (shortName : Name) : MetaM Name := do
  if env.contains shortName then
    return shortName
  let inNs := `CandidateExecutor ++ shortName
  if env.contains inNs then
    return inNs
  throwError s!"Declaration '{shortName}' (or '{inNs}') not found in environment."

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

def runVerifyTarget (frozenTargetName executorName : Name) (prohibited : List Name) : MetaM Unit := do
  let env ← getEnv
  
  -- 1. Existence checks & Name Resolution
  let some targetDecl := env.find? frozenTargetName
    | throwError s!"Target declaration '{frozenTargetName}' not found in environment."
  let executorResolved ← resolveCandidateName env executorName
  let some executorDecl := env.find? executorResolved
    | throwError s!"Executor declaration '{executorResolved}' not found in environment."

  -- 2. Module-Provenance Candidate Enumeration
  let trustedList : List Name := [frozenTargetName, `VerifierTrustCore.runVerifyTarget]
  let candidateDecls := getCandidateDecls env trustedList
  let allDecls := if candidateDecls.contains executorResolved then candidateDecls else executorResolved :: candidateDecls

  -- Method Mode Deny-List Audit across all candidate-authored declarations
  checkDirectProhibited env allDecls prohibited

  -- 3. Definitional equality of full types
  let targetType := targetDecl.type
  let executorType := executorDecl.type
  
  if !(← isDefEq targetType executorType) then
    throwError s!"TYPE_MISMATCH: Executor theorem type does not match frozen target type:\n  Expected: {targetType}\n  Received: {executorType}"

  -- 4. Fail-Closed Axiom Audit
  let axioms ← Lean.collectAxioms executorResolved
  let allowedAxioms : List Name := [`propext, `Classical.choice, `Quot.sound]
  
  for ax in axioms do
    if !allowedAxioms.contains ax then
      throwError s!"FORBIDDEN_AXIOM: Proof transitively relies on non-standard axiom '{ax}'."

  IO.println s!"VERIFICATION_SUCCESS: '{executorResolved}' matches '{frozenTargetName}' definitionally with certified kernel axioms: {axioms.toList}"

end VerifierTrustCore
