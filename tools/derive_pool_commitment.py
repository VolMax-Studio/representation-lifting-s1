#!/usr/bin/env python3
r"""
tools/derive_pool_commitment.py  (amendment v0.21, candidate r2)

Two mechanical steps; nothing in either output is chosen by a human.

1) BEFORE anchoring — build the anchor subject (pool_commitment.json, v2):
     python3 tools/derive_pool_commitment.py commitment \
         --freeze-tag-object-id $(git rev-parse representation-lifting-s1-freeze-v0.21) \
         --manifest <run2>/pool_bundle_manifest.json --pool-tsv <run2>/POOL.tsv --out-dir custody/
   published_at_unix := T_COMMIT_UNIX (pinned in the signed freeze). Refuses after T_COMMIT_UNIX.

2) AFTER `rekor-cli upload` + `rekor-cli verify` + tools/fetch_rekor_evidence.py —
   derive and self-validate pool_anchor_receipt.json (v2):
     python3 tools/derive_pool_commitment.py receipt \
         --commitment custody/pool_commitment.json --rekor-evidence custody/rekor_entry_evidence.json \
         --manifest <run2>/pool_bundle_manifest.json --pool-tsv <run2>/POOL.tsv \
         --verifier "rekor-cli vX.Y.Z verify (exit 0)" --out-dir custody/
"""

import argparse
import hashlib
import json
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import pool_custody  # noqa: E402
from analyze import parse_pool_tsv  # noqa: E402
from drand_schedule import compute_scheduled_round, round_time  # noqa: E402


def _read(p: str) -> bytes:
    with open(p, "rb") as f:
        return f.read()


def _write_new(path: str, data: bytes) -> None:
    if os.path.exists(path):
        raise FileExistsError(f"REFUSING: {path} already exists (custody records are never overwritten).")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="step", required=True)
    c = sub.add_parser("commitment")
    c.add_argument("--freeze-tag-object-id", required=True)
    r = sub.add_parser("receipt")
    r.add_argument("--commitment", required=True)
    r.add_argument("--rekor-evidence", required=True)
    r.add_argument("--verifier", required=True)
    for p in (c, r):
        p.add_argument("--manifest", required=True)
        p.add_argument("--pool-tsv", required=True)
        p.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    manifest = _read(args.manifest)
    pool = _read(args.pool_tsv)
    _, case_ids = parse_pool_tsv(pool)
    pool_sha = hashlib.sha256(pool).hexdigest()

    try:
        if args.step == "commitment":
            commitment = pool_custody.build_commitment(args.freeze_tag_object_id, manifest, pool_sha, len(case_ids))
            t_c = commitment["published_at_unix"]
            now = int(time.time())
            if now >= t_c:
                print(f"REFUSING: now={now} is not before T_COMMIT_UNIX={t_c}; the anchor deadline has passed. "
                      f"H2 is NOT_EVALUABLE_POOL_TIMESTAMP (PREREGISTRATION_v0.21 §3.8).", file=sys.stderr)
                return 2
            data = pool_custody.canonical_json_bytes(commitment)
            out = os.path.join(args.out_dir, "pool_commitment.json")
            _write_new(out, data)
            rnd = compute_scheduled_round(t_c)
            print(f"pool_commitment.json   {out}")
            print(f"subject sha256         {hashlib.sha256(data).hexdigest()}")
            print(f"anchor deadline        T_COMMIT_UNIX = {t_c}  ({t_c - now}s from now)")
            print(f"precommitted round     {rnd}  (publishes at {round_time(rnd)})")
            print("NEXT: ssh-keygen -Y sign -n file ... ; rekor-cli upload ... ; rekor-cli verify ...")
        else:
            commitment = json.loads(_read(args.commitment))
            if pool_custody.canonical_json_bytes(commitment) != _read(args.commitment):
                print("CUSTODY VIOLATION: pool_commitment.json is not in canonical form.", file=sys.stderr)
                return 2
            anchor = pool_custody.derive_anchor_receipt(
                commitment, _read(args.rekor_evidence), args.verifier, manifest, pool_sha, len(case_ids))
            data = pool_custody.canonical_json_bytes(anchor)
            out = os.path.join(args.out_dir, "pool_anchor_receipt.json")
            _write_new(out, data)
            print(f"pool_anchor_receipt    {out}  sha256 {hashlib.sha256(data).hexdigest()}")
            print(f"T1 (integratedTime)    {anchor['integrated_time_unix']}  <= T_COMMIT_UNIX {commitment['published_at_unix']}")
            print(f"drand round            {compute_scheduled_round(commitment['published_at_unix'])}")
    except pool_custody.CustodyError as err:
        print(f"CUSTODY VIOLATION: {err}", file=sys.stderr)
        return 2
    except FileExistsError as err:
        print(str(err), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
