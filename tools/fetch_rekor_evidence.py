#!/usr/bin/env python3
r"""
tools/fetch_rekor_evidence.py  (amendment v0.21)

Archives the raw public Rekor API responses for every transparency-log entry whose
artifact hash equals SHA-256(pool_bundle_manifest.json). Output schema:
representation-lifting-rekor-evidence/v1 (see tools/pool_custody.parse_rekor_evidence).

  python3 tools/fetch_rekor_evidence.py \
      --manifest <path>/pool_bundle_manifest.json \
      --out <path>/rekor_evidence.json

Performs only HTTP GET/POST reads against https://rekor.sigstore.dev. It never uploads.
The output is validated with the same parser analyze.py uses before being written.
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

HttpFn = Callable[[str, str, bytes | None], object]


def _default_http(method: str, url: str, body: bytes | None) -> object:
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        if resp.status != 200:
            raise RuntimeError(f"{method} {url} -> HTTP {resp.status}")
        return json.loads(resp.read().decode("utf-8"))


def build_evidence(manifest_bytes: bytes, http: HttpFn = _default_http, now: int | None = None) -> dict:
    m = pool_custody.sha256_hex(manifest_bytes)
    base = pool_custody.REKOR_LOG_URL
    uuids = http("POST", f"{base}/api/v1/index/retrieve",
                 json.dumps({"hash": f"sha256:{m}"}).encode("utf-8"))
    if not isinstance(uuids, list):
        raise RuntimeError(f"Unexpected index/retrieve response: {uuids!r}")
    entries = [http("GET", f"{base}/api/v1/log/entries/{u}", None) for u in uuids]
    return {
        "schema_version": pool_custody.REKOR_EVIDENCE_SCHEMA_VERSION,
        "rekor_url": base,
        "query_sha256": m,
        "retrieved_at_unix": int(time.time()) if now is None else now,
        "index_retrieve_response": uuids,
        "log_entries": entries,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if os.path.exists(args.out):
        print(f"REFUSING: {args.out} already exists (evidence files are never overwritten).", file=sys.stderr)
        return 2
    with open(args.manifest, "rb") as f:
        manifest_bytes = f.read()
    ev = build_evidence(manifest_bytes)
    data = pool_custody.canonical_json_bytes(ev)
    entries = pool_custody.parse_rekor_evidence(data, ev["query_sha256"])  # fail closed before writing
    with open(args.out, "wb") as f:
        f.write(data)
    print(f"manifest_sha256      {ev['query_sha256']}")
    print(f"entries_found        {len(entries)}")
    for e in entries:
        print(f"  uuid={e['uuid']} logIndex={e['log_index']} integratedTime={e['integrated_time']} kind={e['kind']}")
    print(f"EARLIEST (T1)        {entries[0]['integrated_time']}  uuid={entries[0]['uuid']}")
    print(f"evidence_sha256      {pool_custody.sha256_hex(data)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
