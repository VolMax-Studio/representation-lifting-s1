import Lean

/-!
tools/VerifyTarget.lean
Pure Lean 4 meta-checker for Exact Target Match and Fail-Closed Axiom Audit:
1. Verifies that `frozen_target` and `executor_theorem` are declared.
2. Uses `isDefEq` on their full types:
   asserts type(executor_theorem) ≡_def type(frozen_target).
   Automatically handles binder renaming, implicit binders, dependent Π, existentials.
3. Uses `Lean.collectAxioms` to audit transitive axioms:
   Asserts A_observed ⊆ {propext, Classical.choice, Quot.sound}.
   Rejects sorryAx, custom axioms, or unproved constants.
4. Fail-closed: Any compilation or meta error terminates with non-zero exit code.
Part of representation-lifting-s1 experimental protocol.
-/

open Lean Meta

def runVerifyTarget (frozenTargetName executorName : Name) : MetaM Unit := do
  let env ← getEnv
  
  -- 1. Existence check
  let some targetDecl := env.find? frozenTargetName
    | throwError s!"Target declaration '{frozenTargetName}' not found in environment."
  let some executorDecl := env.find? executorName
    | throwError s!"Executor declaration '{executorName}' not found in environment."

  -- 2. Definitional equality of full types
  let targetType := targetDecl.type
  let executorType := executorDecl.type
  
  if !(← isDefEq targetType executorType) then
    throwError s!"TYPE_MISMATCH: Executor theorem type does not match frozen target type:\n  Expected: {targetType}\n  Received: {executorType}"

  -- 3. Fail-Closed Axiom Audit
  let axioms ← Lean.collectAxioms executorName
  let allowedAxioms : List Name := [`propext, `Classical.choice, `Quot.sound]
  
  for ax in axioms do
    if !allowedAxioms.contains ax then
      throwError s!"FORBIDDEN_AXIOM: Proof transitively relies on non-standard axiom '{ax}'."

  IO.println s!"VERIFICATION_SUCCESS: '{executorName}' matches '{frozenTargetName}' definitionally with certified kernel axioms: {axioms.toList}"
