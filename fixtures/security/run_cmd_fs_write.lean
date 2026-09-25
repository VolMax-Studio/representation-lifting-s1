-- fixtures/security/run_cmd_fs_write.lean
-- Adversarial fixture: Attempts to modify repository files outside temporary build directory.
-- In v0.9, rejected by static defense-in-depth scan and filesystem integrity guard.

import Lean

open Lean

run_cmd do
  IO.FS.writeFile "tools/malicious_hacked.txt" "pwned"
