#!/usr/bin/env python3
r"""
tools/fetch_rekor_evidence.py  (amendment v0.21, candidate r2)

Archives the raw public Rekor API response for the ONE transparency-log entry created when the
ratifier's SSH signature over pool_commitment.json was uploaded (`rekor-cli upload` prints its UUID).
No index search is used: Rekor's /api/v1/index/retrieve is best-effort, deprecated, and may be
incomplete, so it carries no normative weight in this protocol.

  python3 tools/fetch_rekor_evidence.py --uuid <UUID from rekor-cli upload> --out custody/rekor_entry_evidence.json

Output schema: representation-lifting-rekor-entry-evidence/v1 (tools/pool_custody.parse_rekor_entry_evidence).
Performs a single HTTP GET. Never uploads. Never overwrites.
"""

import argparse
import json
import os
import sys
import time
import urllib.request
from typing import Callable

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import pool_custody  # noqa: E402

HttpGet = Callable[[str], object]


def _default_get(url: str) -> object:
    req = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        if resp.status != 200:
            raise RuntimeError(f"GET {url} -> HTTP {resp.status}")
        return json.loads(resp.read().decode("utf-8"))


def build_evidence(uuid: str, get: HttpGet = _default_get, now: int | None = None) -> dict:
    return {
        "schema_version": pool_custody.REKOR_ENTRY_EVIDENCE_SCHEMA_VERSION,
        "rekor_url": pool_custody.REKOR_LOG_URL,
        "requested_uuid": uuid,
        "retrieved_at_unix": int(time.time()) if now is None else now,
        "log_entry": get(f"{pool_custody.REKOR_LOG_URL}/api/v1/log/entries/{uuid}"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--uuid", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if os.path.exists(args.out):
        print(f"REFUSING: {args.out} already exists (evidence files are never overwritten).", file=sys.stderr)
        return 2
    data = pool_custody.canonical_json_bytes(build_evidence(args.uuid))
    with open(args.out, "wb") as f:
        f.write(data)
    print(f"archived   {args.out}")
    print(f"sha256     {pool_custody.sha256_hex(data)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
