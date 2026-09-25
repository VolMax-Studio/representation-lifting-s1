-- fixtures/security/skip_kernel_tc.lean
-- Adversarial fixture: Attempts to disable kernel type checking using debug.skipKernelTC.
-- In v0.9, rejected by static defense-in-depth scan and fail-closed kernel replay.

set_option debug.skipKernelTC true

theorem fake_thm : 1 = 2 := by
  sorry
