#!/usr/bin/env python3
"""
tests/custody_fixtures.py
Synthetic v0.21 custody artifacts (manifest, raw Rekor API evidence, commitment/v2, anchor/v2).

Rekor entry objects mirror the public Rekor v1 API shape
(GET /api/v1/log/entries/{uuid} -> {uuid: {body, integratedTime, logID, logIndex, verification}}).
A captured REAL Rekor response is additionally required as a freeze-gate fixture
(tests/fixtures/rekor_real_entry_dryrun.json, see PREREGISTRATION_v0.21 §9 Gate 3a).
"""

import base64
import hashlib
import json
import os
import sys

TOOLS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, TOOLS_DIR)

import pool_custody  # noqa: E402

LOG_ID = "c0d23d6ad406973f9559f3ba2d1ca01f84147d8ffc5b8445c224f98b9591801d"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def make_manifest_bytes(pool_bytes: bytes, **overrides) -> bytes:
    m = {
        "schema_version": pool_custody.POOL_MANIFEST_SCHEMA_VERSION,
        "builder_name": "tools/build_pool.py",
        "builder_sha256": pool_custody.FROZEN_BUILDER_SHA256,
        "filter_name": "tools/nontriviality_filter.py",
        "filter_sha256": pool_custody.FROZEN_FILTER_SHA256,
        "source_repository": "https://github.com/marcusm117/ProofNet-Verified.git",
        "source_commit": "160414332dc196583f6c37c310b420d2a3b07c58",
        "source_jsonl_sha256": "381f4a06548a4ff6d9b923633c94a97b9c70f41033e13023aae31e1161b7f142",
        "bundle_files": {"POOL.tsv": sha(pool_bytes)},
        "bundle_sha256": "0" * 64,
    }
    m.update(overrides)
    return (json.dumps(m, indent=2, sort_keys=True) + "\n").encode("utf-8")


def make_rekor_entry(uuid: str, artifact_sha: str, integrated_time: int, log_index: int,
                     kind: str = "hashedrekord", with_set: bool = True) -> dict:
    body = {
        "apiVersion": "0.0.1",
        "kind": kind,
        "spec": {
            "data": {"hash": {"algorithm": "sha256", "value": artifact_sha}},
            "signature": {"content": "c2ln", "publicKey": {"content": "cGs="}},
        },
    }
    verification = {"inclusionProof": {"checkpoint": "cp", "hashes": [], "logIndex": log_index,
                                       "rootHash": "00" * 32, "treeSize": log_index + 1}}
    if with_set:
        verification["signedEntryTimestamp"] = "MEUCIQDsyntheticSET"
    return {uuid: {
        "body": base64.b64encode(json.dumps(body).encode("utf-8")).decode("ascii"),
        "integratedTime": integrated_time,
        "logID": LOG_ID,
        "logIndex": log_index,
        "verification": verification,
    }}


def uuid_n(n: int) -> str:
    return hashlib.sha256(f"entry-{n}".encode()).hexdigest()


def make_evidence_bytes(manifest_sha: str, entries: list[dict], retrieved_at: int = 1800000000,
                        index_uuids: list[str] | None = None, **overrides) -> bytes:
    if index_uuids is None:
        index_uuids = [next(iter(e)) for e in entries]
    ev = {
        "schema_version": pool_custody.REKOR_EVIDENCE_SCHEMA_VERSION,
        "rekor_url": pool_custody.REKOR_LOG_URL,
        "query_sha256": manifest_sha,
        "retrieved_at_unix": retrieved_at,
        "index_retrieve_response": index_uuids,
        "log_entries": entries,
    }
    ev.update(overrides)
    return pool_custody.canonical_json_bytes(ev)


def make_valid_custody(pool_bytes: bytes, pool_size: int, t1: int = 1790000000):
    """Returns (manifest_bytes, evidence_bytes, commitment, anchor) for a single-entry anchor at T1."""
    manifest = make_manifest_bytes(pool_bytes)
    m = sha(manifest)
    evidence = make_evidence_bytes(m, [make_rekor_entry(uuid_n(1), m, t1, 1000)])
    commitment, anchor = pool_custody.derive_custody_records(
        manifest, sha(pool_bytes), pool_size, evidence, "rekor-cli v1.3.9 verify (exit 0)",
        expected_manifest_sha256=m)
    return manifest, evidence, commitment, anchor
