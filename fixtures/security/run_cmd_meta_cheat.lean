-- fixtures/security/run_cmd_meta_cheat.lean
-- Adversarial fixture: Attempts to execute arbitrary meta-code and mutate environment during compilation.
-- In v0.9, rejected by static defense-in-depth scan and fail-closed kernel replay.

import Lean

open Lean

run_cmd do
  IO.println "Attempting environment bypass"
