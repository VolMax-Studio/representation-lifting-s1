import Lean

/-!
tools/VerifyLifted.lean
Pure Lean 4 meta-checker for Structural Lifted Proof (Role L) Verification:
1. Verifies existence of:
   - `frozen_target`
   - `BridgeProp` (frozen specification property linking target and LiftedClaim)
   - `LiftedClaim` (frozen closed lifted proposition)
   - `preservation_bridge` (proved bridge theorem)
   - `lifted_theorem` (proved theorem on lifted representation)
2. Type Equivalence Audits:
   - `type(preservation_bridge) ≡_def BridgeProp`
   - `type(lifted_theorem) ≡_def LiftedClaim`
3. Fail-Closed Axiom Audits (zero sorryAx permitted):
   - Transitive axioms of `preservation_bridge` ⊆ {propext, Classical.choice, Quot.sound}
   - Transitive axioms of `lifted_theorem` ⊆ {propext, Classical.choice, Quot.sound}
4. Non-Circularity Provenance Audit:
   - Asserts: `preservation_bridge ∉ Deps(lifted_theorem)`.
   - The lifted claim must be proved autonomously in the lifted representation,
     not circularly through the bridge.
5. Method Mode Deny-List Audit:
   - Direct constant references in candidate declarations cannot match prohibited library constants.
6. Prints strict sentinel: `VERIFY_LIFTED_SENTINEL_OK`.
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

def checkNonCircularity (env : Environment) (liftedThmName bridgeThmName : Name) : MetaM Unit := do
  let some decl := env.find? liftedThmName
    | throwError s!"Declaration '{liftedThmName}' not found."
  if let some val := getDeclValue? decl then
    let consts := val.foldConsts [] (fun c acc => if acc.contains c then acc else c :: acc)
    if consts.contains bridgeThmName then
      throwError s!"CIRCULAR_LIFT_DEPENDENCY: '{liftedThmName}' circularly references '{bridgeThmName}'."

def runVerifyLifted (frozenTargetName bridgePropName liftedClaimName bridgeThmName liftedThmName : Name) (candidateDecls : List Name) (prohibited : List Name) : MetaM Unit := do
  let env ← getEnv

  -- 1. Existence checks
  let some targetDecl := env.find? frozenTargetName
    | throwError s!"Target declaration '{frozenTargetName}' not found in environment."
  let some _ := env.find? bridgePropName
    | throwError s!"Bridge property declaration '{bridgePropName}' not found in environment."
  let some _ := env.find? liftedClaimName
    | throwError s!"Lifted claim declaration '{liftedClaimName}' not found in environment."
  let some bridgeThmDecl := env.find? bridgeThmName
    | throwError s!"Bridge proof declaration '{bridgeThmName}' not found in environment."
  let some liftedThmDecl := env.find? liftedThmName
    | throwError s!"Lifted proof declaration '{liftedThmName}' not found in environment."

  -- 2. Method Mode Deny-List Audit (all candidate declarations)
  let allDecls := bridgeThmName :: liftedThmName :: candidateDecls
  checkDirectProhibited env allDecls prohibited

  -- 3. Non-Circularity Check
  checkNonCircularity env liftedThmName bridgeThmName

  -- 4. Definitional match of types
  let bridgeThmType := bridgeThmDecl.type
  let bridgePropType := mkConst bridgePropName
  if !(← isDefEq bridgeThmType bridgePropType) then
    throwError s!"BRIDGE_PROP_MISMATCH: '{bridgeThmName}' does not prove '{bridgePropName}':\n  Expected: {bridgePropType}\n  Received: {bridgeThmType}"

  let liftedThmType := liftedThmDecl.type
  let liftedClaimType := mkConst liftedClaimName
  if !(← isDefEq liftedThmType liftedClaimType) then
    throwError s!"LIFTED_CLAIM_MISMATCH: '{liftedThmName}' does not prove '{liftedClaimName}':\n  Expected: {liftedClaimType}\n  Received: {liftedThmType}"

  -- 5. Strict Axiom Audit (zero sorryAx, zero non-standard axioms)
  let allowedAxioms : List Name := [`propext, `Classical.choice, `Quot.sound]
  
  let bridgeAxioms ← Lean.collectAxioms bridgeThmName
  for ax in bridgeAxioms do
    if !allowedAxioms.contains ax then
      throwError s!"FORBIDDEN_AXIOM: Bridge proof '{bridgeThmName}' transitively relies on axiom '{ax}'."

  let liftedAxioms ← Lean.collectAxioms liftedThmName
  for ax in liftedAxioms do
    if !allowedAxioms.contains ax then
      throwError s!"FORBIDDEN_AXIOM: Lifted proof '{liftedThmName}' transitively relies on axiom '{ax}'."

  IO.println s!"VERIFY_LIFTED_SENTINEL_OK"
