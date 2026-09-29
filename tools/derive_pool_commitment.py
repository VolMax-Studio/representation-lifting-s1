#!/usr/bin/env python3
r"""
tools/derive_pool_commitment.py  (amendment v0.21)

Mechanically derives pool_commitment.json (v2) and pool_anchor_receipt.json (v2) from:
  - the carried-forward pool_bundle_manifest.json and POOL.tsv,
  - the archived raw Rekor evidence (tools/fetch_rekor_evidence.py),
  - the name/version of the external tool that verified the Rekor entry
    (`rekor-cli verify`), recorded as `verifier`.

published_at_unix is NEVER chosen by a human: it is T1, the integratedTime of the earliest
Rekor entry for SHA-256(manifest). The tool prints the drand round scheduled from T1 and
that round's publication time. Once M is anchored no free parameter remains.

  python3 tools/derive_pool_commitment.py \
      --manifest ../representation-lifting-s1-pool-run2/pool_bundle_manifest.json \
      --pool-tsv ../representation-lifting-s1-pool-run2/POOL.tsv \
      --rekor-evidence custody/rekor_evidence.json \
      --verifier "rekor-cli v1.x.y verify (exit 0)" \
      --out-dir custody/
"""

import argparse
import hashlib
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import pool_custody  # noqa: E402
from analyze import parse_pool_tsv  # noqa: E402
from drand_schedule import compute_scheduled_round, round_time  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--pool-tsv", required=True)
    ap.add_argument("--rekor-evidence", required=True)
    ap.add_argument("--verifier", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    out_c = os.path.join(args.out_dir, "pool_commitment.json")
    out_a = os.path.join(args.out_dir, "pool_anchor_receipt.json")
    for p in (out_c, out_a):
        if os.path.exists(p):
            print(f"REFUSING: {p} already exists (custody records are never overwritten).", file=sys.stderr)
            return 2

    with open(args.manifest, "rb") as f:
        manifest_bytes = f.read()
    with open(args.pool_tsv, "rb") as f:
        pool_bytes = f.read()
    with open(args.rekor_evidence, "rb") as f:
        evidence_bytes = f.read()

    _, case_ids = parse_pool_tsv(pool_bytes)
    pool_sha = hashlib.sha256(pool_bytes).hexdigest()

    try:
        commitment, anchor = pool_custody.derive_custody_records(
            manifest_bytes, pool_sha, len(case_ids), evidence_bytes, args.verifier)
    except pool_custody.CustodyError as err:
        print(f"CUSTODY VIOLATION: {err}", file=sys.stderr)
        return 2

    t1 = commitment["published_at_unix"]
    rnd = compute_scheduled_round(t1)
    rnd_t = round_time(rnd)
    now = int(time.time())
    # Derivation timing carries no custody weight: T1 is fixed by the public log and every
    # downstream value (round, randomness, indices) is a deterministic function of it.

    os.makedirs(args.out_dir, exist_ok=True)
    with open(out_c, "wb") as f:
        f.write(pool_custody.canonical_json_bytes(commitment))
    with open(out_a, "wb") as f:
        f.write(pool_custody.canonical_json_bytes(anchor))

    print(f"T1 (published_at_unix)  {t1}")
    print(f"scheduled drand round   {rnd}")
    print(f"round publication unix  {rnd_t}   ({rnd_t - now}s from now)")
    print(f"pool_commitment.json    {hashlib.sha256(open(out_c, 'rb').read()).hexdigest()}")
    print(f"pool_anchor_receipt     {hashlib.sha256(open(out_a, 'rb').read()).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
