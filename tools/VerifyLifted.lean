import Lean

/-!
tools/VerifyLifted.lean
Pure Lean 4 meta-checker for Lifted Proof (Role L) Verification & Provenance:
1. Verifies existence of:
   - `frozen_target`
   - `BridgeProp` (frozen specification property)
   - `preservation_bridge` (proved bridge theorem)
   - `executor_theorem` (final target proof)
2. Type Equivalence Audits:
   - `type(preservation_bridge) ≡_def BridgeProp`
   - `type(executor_theorem) ≡_def type(frozen_target)`
3. Fail-Closed Axiom Audits (zero sorryAx permitted):
   - Transitive axioms of `preservation_bridge` ⊆ {propext, Classical.choice, Quot.sound}
   - Transitive axioms of `executor_theorem` ⊆ {propext, Classical.choice, Quot.sound}
4. Proof-of-Method Provenance (Transitive Dependency Audit):
   - Computes transitive dependency closure of `executor_theorem`.
   - Requires: `preservation_bridge ∈ Deps*(executor_theorem)`.
   - Rejects unlinked direct proofs with `LIFT_NOT_USED`.
5. Prints strict sentinel: `VERIFY_LIFTED_SENTINEL_OK`.
Part of representation-lifting-s1 experimental protocol (v0.5).
-/

set_option linter.unusedVariables false

open Lean Meta

partial def collectTransitiveDeps (env : Environment) (start : Name) : List Name :=
  let rec loop (queue : List Name) (visited : List Name) : List Name :=
    match queue with
    | [] => visited
    | c :: rest =>
      if visited.contains c then
        loop rest visited
      else
        let newVisited := c :: visited
        match env.find? c with
        | some (.defnInfo val) =>
          let nexts := val.value.foldConsts [] (fun n acc => if acc.contains n then acc else n :: acc)
          loop (rest ++ nexts) newVisited
        | some (.thmInfo val) =>
          let nexts := val.value.foldConsts [] (fun n acc => if acc.contains n then acc else n :: acc)
          loop (rest ++ nexts) newVisited
        | _ => loop rest newVisited
  loop [start] []

def runVerifyLifted (frozenTargetName bridgePropName bridgeThmName executorName : Name) : MetaM Unit := do
  let env ← getEnv

  -- 1. Existence checks
  let some targetDecl := env.find? frozenTargetName
    | throwError s!"Target declaration '{frozenTargetName}' not found in environment."
  let some _ := env.find? bridgePropName
    | throwError s!"Bridge property declaration '{bridgePropName}' not found in environment."
  let some bridgeThmDecl := env.find? bridgeThmName
    | throwError s!"Bridge proof declaration '{bridgeThmName}' not found in environment."
  let some executorDecl := env.find? executorName
    | throwError s!"Executor declaration '{executorName}' not found in environment."

  -- 2. Definitional match of types
  let bridgeThmType := bridgeThmDecl.type
  let bridgePropType := mkConst bridgePropName
  if !(← isDefEq bridgeThmType bridgePropType) then
    throwError s!"BRIDGE_PROP_MISMATCH: '{bridgeThmName}' does not prove '{bridgePropName}':\n  Expected: {bridgePropType}\n  Received: {bridgeThmType}"

  let executorType := executorDecl.type
  let targetType := targetDecl.type
  if !(← isDefEq executorType targetType) then
    throwError s!"TARGET_TYPE_MISMATCH: '{executorName}' does not match '{frozenTargetName}':\n  Expected: {targetType}\n  Received: {executorType}"

  -- 3. Strict Axiom Audit (zero sorryAx, zero non-standard axioms)
  let allowedAxioms : List Name := [`propext, `Classical.choice, `Quot.sound]
  
  let bridgeAxioms ← Lean.collectAxioms bridgeThmName
  for ax in bridgeAxioms do
    if !allowedAxioms.contains ax then
      throwError s!"FORBIDDEN_AXIOM: Bridge proof '{bridgeThmName}' transitively relies on axiom '{ax}'."

  let executorAxioms ← Lean.collectAxioms executorName
  for ax in executorAxioms do
    if !allowedAxioms.contains ax then
      throwError s!"FORBIDDEN_AXIOM: Executor proof '{executorName}' transitively relies on axiom '{ax}'."

  -- 4. Proof-of-Method Provenance: Transitive Dependency Audit
  let transitiveDeps := collectTransitiveDeps env executorName
  if !transitiveDeps.contains bridgeThmName then
    throwError s!"LIFT_NOT_USED: Proof-of-method provenance failed. Executor theorem '{executorName}' does not transitively depend on '{bridgeThmName}'."

  IO.println s!"VERIFY_LIFTED_SENTINEL_OK"
