# Live Execution Record: Local Pool Build 001 (Aborted on INFRA_HANG)

## Metadata & Pinned State

- **Protocol Version:** `v0.20`
- **Frozen Commit:** `f3c8978b55985c0fc76a71ab3d57ba90917204e1`
- **Signed Tag:** `representation-lifting-s1-freeze-v0.20`
- **ProofNet Upstream Commit:** `160414332dc196583f6c37c310b420d2a3b07c58`
- **ProofNet JSONL Path:** `/home/volmax-studio/volmax-projects/iot2/ARCHIVE_EXTERNAL/ProofNet-Verified/data/proofnet-verified.jsonl`
- **ProofNet JSONL SHA-256:** `381f4a06548a4ff6d9b923633c94a97b9c70f41033e13023aae31e1161b7f142`
- **Total Corpus Records Evaluated:** `367 / 367`

---

## Execution Environment

- **Host Hardware:** HP 470 17 inch G9 Notebook PC
- **CPU:** 12th Gen Intel(R) Core(TM) i7-1255U (10 cores: 2 P-cores, 8 E-cores, 12 threads)
- **RAM / Swap:** 16 GiB RAM, 6.5 GiB Swap
- **Operating System:** Ubuntu 24.04.4 LTS (`noble`, Linux kernel `7.0.0-31-generic` x86_64)
- **Lean Toolchain:** Lean `v4.34.0` (commit `293d5d0c0c3f3dded4688b3ccd6a33939ac5102b`, Release)
- **Lake Version:** `5.0.0-src+293d5d0`
- **Python Version:** `3.12.3`
- **Deterministic Limits:** `maxHeartbeats = 200000`
- **Watchdog Timeout:** `600s` wall-clock per tactic probe

---

## Execution Command

```bash
python3 -u tools/build_pool.py \
  --source /home/volmax-studio/volmax-projects/iot2/ARCHIVE_EXTERNAL/ProofNet-Verified/data/proofnet-verified.jsonl \
  --outdir ../representation-lifting-s1-pool-run1
```
(Invoked via pipe with stdout/stderr captured to `build_pool.execution.log` and exit status recorded to `build_pool.exitcode`).

---

## Result & Partition Outcome

- **Execution Result:** `ABORTED / INFRA_HANG / NO VALID POOL`
- **Builder Exit Code:** `2`
- **Total INFRA_HANG Cases:** `N_INFRA_HANG = 8`
- **Pool TSV Status:** Correctly suppressed (`POOL.tsv` does not exist; verified by `test ! -e ../representation-lifting-s1-pool-run1/POOL.tsv`)
- **Bundle Manifest Status:** Not generated (`pool_bundle_manifest.json` does not exist)
- **Downstream Protocol Invariant:** No pool commitment, timestamp, drand beacon round, blind selection, or experimental outcome was produced. No partial or contaminated data leaked forward.

---

## Hang Breakdown (8 Cases)

| Case ID | Source Name | Reason |
| :--- | :--- | :--- |
| `proofnet-062` | `Dummit_Foote_exercise_7_3_37` | `watchdog_timeout_on_baseline (>600s)` |
| `proofnet-117` | `Munkres_exercise_22_2b` | `watchdog_timeout_on_ring (>600s)` |
| `proofnet-118` | `Munkres_exercise_23_2` | `watchdog_timeout_on_baseline (>600s)` |
| `proofnet-119` | `Munkres_exercise_23_4` | `watchdog_timeout_on_baseline (>600s)` |
| `proofnet-158` | `Rudin_exercise_3_1a` | `watchdog_timeout_on_ring (>600s)` |
| `proofnet-159` | `Rudin_exercise_3_3` | `watchdog_timeout_on_baseline (>600s)` |
| `proofnet-160` | `Rudin_exercise_3_6a` | `watchdog_timeout_on_baseline (>600s)` |
| `proofnet-162` | `Rudin_exercise_3_20` | `watchdog_timeout_on_rfl (>600s)` |

---

## Strict Audit & Methodological Interpretation

- **Observed:** The frozen v0.20 pool builder completed the live corpus evaluation and detected eight wall-clock watchdog expirations on this host. In accordance with the preregistered fail-closed rule, it emitted no `POOL.tsv` and exited with status 2.
- **Not demonstrated:** The cause of the timeouts, machine-independent pool composition, or any representation-lifting effect.

This record serves as live operational qualification and post-freeze audit evidence demonstrating the mechanical integrity of the fail-closed safeguard: when an execution environment fails strict machine-independence guarantees (due to host suspension, thermal throttling, or resource exhaustion), the instrument unconditionally aborts and prevents invalid pool construction.
