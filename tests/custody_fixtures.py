#!/usr/bin/env python3
"""
tests/custody_fixtures.py
Synthetic v0.21 (r2) custody artifacts: manifest, anchor subject (pool_commitment/v2),
raw Rekor `rekord` entry response for an SSH signing event, anchor receipt/v2.

Entry objects mirror the public Rekor v1 API (GET /api/v1/log/entries/{uuid}) and the
canonical rekord body (spec.data.hash, spec.signature.{format, content, publicKey.content}),
where the SSH public key is canonicalized by Rekor to ssh.MarshalAuthorizedKey form (no comment).
A captured REAL Rekor response is required as freeze-gate fixture
tests/fixtures/rekor_real_entry_dryrun.json (PREREGISTRATION_v0.21 §9 Gate 3a).
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
RATIFIER_KEY = "ssh-ed25519 " + base64.b64encode(b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20" + b"R" * 32).decode()
OTHER_KEY = "ssh-ed25519 " + base64.b64encode(b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20" + b"X" * 32).decode()
FREEZE_TAG = "1f" * 20


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def uuid_n(n: int) -> str:
    return hashlib.sha256(f"entry-{n}".encode()).hexdigest()


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
                     key_line: str = RATIFIER_KEY, kind: str = "rekord", sig_format: str = "ssh",
                     with_set: bool = True, proof_overrides: dict | None = None) -> dict:
    body = {
        "apiVersion": "0.0.1",
        "kind": kind,
        "spec": {
            "data": {"hash": {"algorithm": "sha256", "value": artifact_sha}},
            "signature": {
                "format": sig_format,
                "content": base64.b64encode(b"-----BEGIN SSH SIGNATURE-----\nU1NIU0lH\n-----END SSH SIGNATURE-----\n").decode(),
                "publicKey": {"content": base64.b64encode((key_line + "\n").encode()).decode()},
            },
        },
    }
    proof = {"checkpoint": "rekor.sigstore.dev - 1193050959916656506\n", "hashes": ["ab" * 32],
             "logIndex": log_index, "rootHash": "cd" * 32, "treeSize": log_index + 5}
    proof.update(proof_overrides or {})
    verification = {"inclusionProof": proof}
    if with_set:
        verification["signedEntryTimestamp"] = "MEUCIQDsyntheticSET"
    return {uuid: {
        "body": base64.b64encode(json.dumps(body).encode("utf-8")).decode("ascii"),
        "integratedTime": integrated_time,
        "logID": LOG_ID,
        "logIndex": log_index,
        "verification": verification,
    }}


def make_evidence_bytes(entry: dict, requested_uuid: str | None = None, **overrides) -> bytes:
    ev = {
        "schema_version": pool_custody.REKOR_ENTRY_EVIDENCE_SCHEMA_VERSION,
        "rekor_url": pool_custody.REKOR_LOG_URL,
        "requested_uuid": requested_uuid or next(iter(entry)),
        "retrieved_at_unix": 1700000000,   # informational only; deliberately earlier than T1 (no skew check)
        "log_entry": entry,
    }
    ev.update(overrides)
    return pool_custody.canonical_json_bytes(ev)


def make_valid_custody(pool_bytes: bytes, pool_size: int, t_commit: int = 1790000000, t1: int | None = None):
    """Returns (manifest_bytes, evidence_bytes, commitment, anchor) with the entry at T1 <= T_commit."""
    t1 = t_commit - 3600 if t1 is None else t1
    manifest = make_manifest_bytes(pool_bytes)
    m = sha(manifest)
    commitment = pool_custody.build_commitment(FREEZE_TAG, manifest, sha(pool_bytes), pool_size,
                                               t_commit=t_commit, expected_manifest_sha256=m)
    subject = sha(pool_custody.canonical_json_bytes(commitment))
    evidence = make_evidence_bytes(make_rekor_entry(uuid_n(1), subject, t1, 1000))
    anchor = pool_custody.derive_anchor_receipt(
        commitment, evidence, "rekor-cli v1.3.9 verify (exit 0)", manifest, sha(pool_bytes), pool_size,
        expected_manifest_sha256=m, t_commit=t_commit, ratifier_key=RATIFIER_KEY)
    return manifest, evidence, commitment, anchor
