# Deviation Record — Blind Execution Before A1 Ratification

**Study:** representation-lifting-s1 (frozen v0.21, tag `representation-lifting-s1-freeze-v0.21` → `a3736d2`)
**Amendment concerned:** `AMENDMENT_A1_TRANSPORT.md` (candidate, last commit `b02486b`)
**Recorded:** 2026-10-04T14:44:00Z
**Recorded by:** Ivan Nestorov (principal investigator)
**Outcome visibility at time of recording:** NONE. No execution receipt, bridge response, transcript, proof
text or status from the blind batch has been opened, printed, summarized or otherwise inspected by any
human or agent.

---

## 1. Facts

1. §A1.18 requires, in this order: candidate commit → independent review of the exact candidate commit →
   signed annotated tag by the PI → Gate 5 → S/D/L execution. It states: "No other ratification form is
   sufficient."
2. At the time Gate 5 and the blind batch were run:
   - no A1 tag existed, locally or on the remote (`git tag -l '*a1*' '*A1*'` returned nothing);
   - no written independent review of the exact commit `b02486b` existed;
   - `evidence/amendment_a1/a1_transport_config.json` carried
     `"status": "PRIMARY_READY_FOR_REVIEW__REPLICATION_NOT_EVALUABLE_INFRA_DEFERRED"`, not a ratified status.
3. Gate 5 (neutral probe, `claude-sonnet-4-6`, exact match, `tools: []`, `mcp_servers: []`) was executed and
   committed as `4a2cd67`, which was pushed only after the blind batch had been launched.
4. The blind batch (`proofnet-108`, `proofnet-083`, `proofnet-267`; frozen harness `run_blind_case`;
   `claude-sonnet-4-6` via the A1 Claude Code CLI bridge, `effort: high`) was launched as background task
   `task-5524` at 2026-10-04T14:28:01Z.

## 2. Classification (binding, made before any outcome is visible)

The blind batch launched as `task-5524`, and Gate 5 commit `4a2cd67`, are classified as

> **INVALID_PRE_RATIFICATION — not admissible for any hypothesis (H0, H1, H2), any metric, or any
> claim of representation-lifting-s1.**

This classification is final. It does not depend on, and will not be revisited in light of, the content
of the sealed outputs.

## 3. Pre-outcome commitments (binding)

1. **Sealing.** All outputs of `task-5524` are sealed per §4 without being read.
2. **Non-substitution.** The sealed run never substitutes for, supplements, pools with, or "rescues" an
   admissible run, whatever either run's outcome.
3. **No early opening.** The sealed bundle stays closed until the admissible blind, control and
   calibration receipts for s1 are committed and pushed, or until s1 is formally closed as
   `NOT_EVALUABLE`. Only then may it be opened, and only as a disclosed, non-inferential exploratory record.
4. **Single admissible run.** After proper ratification (§6), exactly one admissible execution of the
   three selected cases is performed under the ratified configuration. Its receipts are final under
   §A1.12 (no regeneration, no selection among runs).
5. **Fixed configuration.** The ratified A1 configuration is fixed without access to the sealed outputs.
   Any difference from `b02486b` is listed explicitly in the ratified candidate.
6. **Failure path.** If an admissible run cannot be executed (e.g. `claude-sonnet-4-6` becomes
   unavailable, §A1.14), H2 for s1 is `NOT_EVALUABLE_INFRA`. The sealed run does not become admissible
   under any circumstance.
7. **Selection unchanged.** Pool (`aef332…`/`398ddc…`, N = 362), anchor, Quicknet round 32691613 and the
   selected cases are unaffected. The selection is not redrawn.

## 4. Sealing procedure (no content may be printed)

Executed after `task-5524` terminates (normally or by operator termination; record which).
Only path-only filesystem operations required for sealing may touch the files: `ls`/enumeration, `mkdir`,
`tar`, `sha256sum`, `rm` after successful archive creation, and `git`. Content-reading tools are prohibited
on these paths, including `cat`, `head`, `tail`, `less`, `grep`, editors, JSON parsers and any agent "View"
action.

```bash
SEAL=../rl-s1-sealed-invalid-pre-ratification
mkdir -p "$SEAL"
# 1. enumerate every artifact written by task-5524 (receipts, bridge requests/responses, logs, temp dirs)
#    by path only, e.g. tools/execution_receipt_blind_*, evidence/amendment_a1/<blind-run dirs>, task log
# 2. move them out of the working tree into a single archive, without reading
tar --sort=name --mtime='UTC 1970-01-01' --owner=0 --group=0 --numeric-owner \
    -cf "$SEAL/sealed_run.tar" <listed paths> && rm -rf <listed paths>
sha256sum "$SEAL/sealed_run.tar" > "$SEAL/sealed_run.tar.sha256"
tar -tf "$SEAL/sealed_run.tar" > "$SEAL/sealed_run.filelist.txt"   # names only
```

Committed to the repository: `sealed_run.tar.sha256`, `sealed_run.filelist.txt`, the task exit status,
and start/end UTC times. **The tar itself is not committed** (a public commit would expose the contents);
it stays offline until §3.3 is satisfied and is then published so that its hash can be checked.

## 5. Provenance items recorded with this deviation

1. **Index mapping.** Target preparation first read ProofNet JSONL entries by `index` 105, 80 and 261
   (the 0-based `POOL.tsv` row positions) instead of the canonical ProofNet indices 108, 83 and 267. Those
   three wrong targets were written and elaborated, and the names of the three non-selected entries were
   printed. They were overwritten before launch. The final `targets/*.lean` were then regenerated
   deterministically by `tools/prepare_blind_targets.py` and are byte-identical to the files used by
   `task-5524`:
   - `proofnet-083` `507b4860cde42100ac319d4d9452b2e418de9bf1de67d0a2b9ab651d7732fd51`
   - `proofnet-108` `8b0776c182dd39259dbb2a19037c2214a3322a95f0ab808748f699967f2213f9`
   - `proofnet-267` `2eb7cdde40626e120d46eecba2c58c230298ca986e7589c38ef2db88e4879a89`

   `tools/prepare_blind_targets.py` was written after launch, is not part of any ratified protocol, and is
   submitted for review with the A1 candidate (§6).
2. **Operator-agent exposure.** While checking the declaration format, the operator agent (not the
   executor) displayed `head -n 3` / `tail -n 2` of the archived ProofNet-Verified file
   `proofnet-verified/proofnet-108.lean`, which contains a verified proof, and grepped its declaration
   line. The executor had no file or tool access (Gate 5: `tools: []`, `mcp_servers: []`, sanitized
   temporary cwd). No human operator read it.
3. **Post-selection adoption of A1.** A1 (first commit 2026-10-02) and its pinned `effort: high` were
   adopted after the Quicknet selection (2026-10-01), when the identifiers and source names of the
   selected cases were already public in the evidence. The operator states that no problem-specific
   prompt or parameter was introduced. This is verified by hashing the protocol prompts used against
   the frozen `tools/executor_harness.py` in the review of §6.
4. **State-machine wording.** A1.19 says "S→D→L". The frozen `tools/executor_harness.py::run_blind_case`
   executes D → S → L with in-memory D custody, consistent with preregistration §4.5. The frozen harness
   is normative; the A1 wording is corrected in the candidate.
5. **Generation-control degradations under A1** (unchanged by this deviation; reported as limitations):
   no temperature control, surface-default max tokens, history flattened to user content; replication
   (`gpt-5.6-sol`) `NOT_EVALUABLE_INFRA`, deferred.

## 6. Remediation path

1. A1 candidate r6 = `b02486b` + this record + `tools/prepare_blind_targets.py` (with tests) + A1.19
   wording fix + `a1_transport_config.json` with Gate-5 configuration hashes. No other change.
2. Written independent review of the exact r6 commit, archived in `evidence/`.
3. Signed annotated tag by the PI on the reviewed commit.
4. **Gate 5 repeated** after the tag (the pre-ratification Gate 5 in `4a2cd67` does not satisfy §A1.18).
5. Admissible execution under the ratified configuration: negative control, calibration families and
   the three blind cases. Without the control receipt, `tools/analyze.py` returns
   `INVALIDATED_CONTROL_MISSING`.
6. Analysis via `tools/analyze.py` with the full custody chain; this deviation is cited in the study report.

## 7. Unaffected

Frozen v0.21 tag and commit; pool, manifest and anchor (Gate 3d); Quicknet round 32691613 and its
BLS-verified randomness; selection `[105, 80, 261] → [proofnet-108, proofnet-083, proofnet-267]`;
hypotheses, scoring, control veto and verdict governance.
