import Lean

/-!
tools/VerifyTarget.lean
Pure Lean 4 meta-checker for Exact Target Match, Axiom Audit, and Method Mode Deny-List:
1. Verifies that `frozen_target` and `executor_theorem` are declared.
2. Uses `isDefEq` on their full types:
   asserts type(executor_theorem) ≡_def type(frozen_target).
   Automatically handles binder renaming, implicit binders, dependent Π, existentials.
3. Strict Kernel Axiom Audit:
   Asserts A_observed ⊆ {propext, Classical.choice, Quot.sound}.
   Rejects sorryAx, custom axioms, or unproved constants.
4. Method Mode Deny-List Enforcement:
   Inspects direct constant references in executor_theorem against prohibited library lemmas.
   Rejects direct references to forbidden terminal lemmas with FORBIDDEN_METHOD_MODE_CONSTANT.
5. Fail-closed: Any compilation or meta error terminates with non-zero exit code.
Part of representation-lifting-s1 experimental protocol (v0.6).
-/

set_option linter.unusedVariables false

open Lean Meta

def getDeclValue? (decl : ConstantInfo) : Option Expr :=
  match decl with
  | .thmInfo v => some v.value
  | .defnInfo v => some v.value
  | _ => none

def checkDirectProhibited (env : Environment) (declNames : List Name) (prohibited : List Name) : MetaM Unit := do
  if prohibited.isEmpty then return ()
  for d in declNames do
    if let some decl := env.find? d then
      if let some val := getDeclValue? decl then
        let consts := val.foldConsts [] (fun c acc => if acc.contains c then acc else c :: acc)
        for c in consts do
          if prohibited.contains c then
            throwError s!"FORBIDDEN_METHOD_MODE_CONSTANT: Declaration '{d}' directly references prohibited constant '{c}'."

def runVerifyTarget (frozenTargetName executorName : Name) (candidateDecls : List Name) (prohibited : List Name) : MetaM Unit := do
  let env ← getEnv
  
  -- 1. Existence check
  let some targetDecl := env.find? frozenTargetName
    | throwError s!"Target declaration '{frozenTargetName}' not found in environment."
  let some executorDecl := env.find? executorName
    | throwError s!"Executor declaration '{executorName}' not found in environment."

  -- 2. Method Mode Deny-List Audit (checks executorName and all helper declarations)
  let allDecls := executorName :: candidateDecls
  checkDirectProhibited env allDecls prohibited

  -- 3. Definitional equality of full types
  let targetType := targetDecl.type
  let executorType := executorDecl.type
  
  if !(← isDefEq targetType executorType) then
    throwError s!"TYPE_MISMATCH: Executor theorem type does not match frozen target type:\n  Expected: {targetType}\n  Received: {executorType}"

  -- 4. Fail-Closed Axiom Audit
  let axioms ← Lean.collectAxioms executorName
  let allowedAxioms : List Name := [`propext, `Classical.choice, `Quot.sound]
  
  for ax in axioms do
    if !allowedAxioms.contains ax then
      throwError s!"FORBIDDEN_AXIOM: Proof transitively relies on non-standard axiom '{ax}'."

  IO.println s!"VERIFICATION_SUCCESS: '{executorName}' matches '{frozenTargetName}' definitionally with certified kernel axioms: {axioms.toList}"
