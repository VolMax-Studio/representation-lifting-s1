#!/usr/bin/env python3
r"""
tools/pool_custody.py
Pre-randomness pool custody for representation-lifting-s1 (amendment v0.21).

Normative chain (PREREGISTRATION_v0.21 §3.5):

    pool_bundle_manifest.json bytes
        -> M = SHA-256(manifest bytes)
        -> public Rekor transparency-log entries whose artifact hash is M
        -> T1 = integratedTime of the EARLIEST such entry (ties: lowest logIndex)
        -> pool_commitment.json (v2):      published_at_unix := T1   (derived, never hand-authored)
        -> pool_anchor_receipt.json (v2):  verified_timestamp_unix := T1
        -> drand round r = compute_scheduled_round(T1)

Why the EARLIEST entry: the drand round is a function of T1. If an operator could
choose among several anchors of M, they could choose among several rounds after seeing
their randomness ("anchor grinding"). Rekor is a public, append-only log searchable by
artifact hash, so every earlier anchor of M is discoverable by anyone, and the earliest
one is authoritative regardless of who created it.

This module performs STRUCTURAL and BINDING validation of the archived raw Rekor API
responses (hash binding, time extraction, earliest-entry selection, receipt/commitment
consistency). Cryptographic verification of the Rekor Signed Entry Timestamp and
inclusion proof is performed externally with `rekor-cli verify` and recorded in the
receipt's `verifier` field, consistent with the analysis boundary of §3.3.

No function in this module touches pool construction. The carried-forward pool is pinned.
"""

import base64
import hashlib
import json
import re
from typing import Any

POOL_COMMITMENT_SCHEMA_VERSION_V2 = "representation-lifting-pool-commitment/v2"
POOL_ANCHOR_SCHEMA_VERSION_V2 = "representation-lifting-pool-anchor/v2"
REKOR_EVIDENCE_SCHEMA_VERSION = "representation-lifting-rekor-evidence/v1"
POOL_MANIFEST_SCHEMA_VERSION = "representation-lifting-pool-bundle-manifest/v1"

RETIRED_SCHEMA_VERSIONS = {
    "representation-lifting-pool-commitment/v1",
    "representation-lifting-pool-anchor/v1",
}

REKOR_LOG_URL = "https://rekor.sigstore.dev"
ANCHOR_TYPE_REKOR = "rekor"
ALLOWED_REKOR_KINDS = {"rekord", "hashedrekord"}

# Carried-forward candidate pool (run2, frozen v0.20 builder f3c8978). v0.21 has no
# authority to regenerate or replace it; any other manifest is rejected.
CARRIED_FORWARD_MANIFEST_SHA256 = "aef332f69fb7bf70c0032dc05a383f8fea0085fecbd2ba22281c48ef4c36f7f6"
CARRIED_FORWARD_POOL_SHA256 = "398ddcb3d9e915edce681c0d59138950177d7eb096200795f927741fb9743212"
CARRIED_FORWARD_POOL_SIZE = 362

# Frozen v0.20 instrument identity (SHA-256 of file bytes at commit f3c8978).
FROZEN_BUILDER_SHA256 = "fccafe9e5a968098d99c7bd00015885c75be506c88854f220060862a8f7e3a65"
FROZEN_FILTER_SHA256 = "de48d2c28a735d0128e49a3a714708bf8fe1cf60cff20a70cff251649d921fdf"

COMMITMENT_V2_KEYS = {"schema_version", "manifest_sha256", "pool_sha256", "pool_size", "published_at_unix"}
ANCHOR_V2_KEYS = {
    "schema_version", "anchor_type", "rekor_url", "manifest_sha256", "pool_sha256",
    "anchor_proof_id", "anchor_log_index", "verified_timestamp_unix",
    "anchor_evidence_sha256", "verifier", "verification_status",
}

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class CustodyError(ValueError):
    """Raised on any violation of the v0.21 pre-randomness custody contract."""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_strict_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _require_hex64(v: Any, what: str) -> str:
    if not isinstance(v, str) or not _HEX64.match(v):
        raise CustodyError(f"{what} must be a lowercase 64-character SHA-256 hex string, got {v!r}.")
    return v


def _uuid_key(u: Any) -> str:
    """Rekor entry UUIDs may carry a 16-hex tree-ID prefix; the last 64 hex chars identify the entry."""
    if not isinstance(u, str) or not re.fullmatch(r"[0-9a-fA-F]{64}|[0-9a-fA-F]{80}", u):
        raise CustodyError(f"Malformed Rekor entry UUID: {u!r}")
    return u.lower()[-64:]


def _reject_retired(schema: Any, what: str) -> None:
    if schema in RETIRED_SCHEMA_VERSIONS:
        raise CustodyError(
            f"{what} uses retired schema '{schema}'. The v0.20 anchor contract was superseded by "
            f"amendment v0.21 (circular published_at_unix / anchor-time semantics); v1 artifacts are not admissible."
        )


def parse_manifest(manifest_bytes: bytes) -> dict:
    if not isinstance(manifest_bytes, (bytes, bytearray)):
        raise CustodyError("pool_bundle_manifest.json must be supplied as raw bytes.")
    try:
        manifest = json.loads(bytes(manifest_bytes).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise CustodyError(f"pool_bundle_manifest.json is not valid UTF-8 JSON: {err}")
    if not isinstance(manifest, dict):
        raise CustodyError("pool_bundle_manifest.json must be a JSON object.")
    if manifest.get("schema_version") != POOL_MANIFEST_SCHEMA_VERSION:
        raise CustodyError(
            f"Manifest schema_version mismatch: expected '{POOL_MANIFEST_SCHEMA_VERSION}', got '{manifest.get('schema_version')}'."
        )
    files = manifest.get("bundle_files")
    if not isinstance(files, dict):
        raise CustodyError("Manifest missing 'bundle_files' object.")
    _require_hex64(files.get("POOL.tsv"), "manifest bundle_files['POOL.tsv']")
    if manifest.get("builder_sha256") != FROZEN_BUILDER_SHA256:
        raise CustodyError(
            f"Manifest builder_sha256 '{manifest.get('builder_sha256')}' is not the frozen v0.20 builder '{FROZEN_BUILDER_SHA256}'."
        )
    if manifest.get("filter_sha256") != FROZEN_FILTER_SHA256:
        raise CustodyError(
            f"Manifest filter_sha256 '{manifest.get('filter_sha256')}' is not the frozen v0.20 filter '{FROZEN_FILTER_SHA256}'."
        )
    return manifest


def parse_rekor_evidence(evidence_bytes: bytes, manifest_sha256: str) -> list[dict]:
    """
    Parses the archived raw Rekor API responses and returns every entry for M as
    [{'uuid', 'log_index', 'integrated_time', 'kind'}], sorted earliest-first.

    Evidence file schema (representation-lifting-rekor-evidence/v1):
      {
        "schema_version": "representation-lifting-rekor-evidence/v1",
        "rekor_url": "https://rekor.sigstore.dev",
        "query_sha256": "<M>",
        "retrieved_at_unix": <int>,
        "index_retrieve_response": <raw JSON of POST /api/v1/index/retrieve {"hash": "sha256:<M>"}>,
        "log_entries": [<raw JSON of GET /api/v1/log/entries/{uuid}>, ...]   # one per UUID
      }
    """
    if not isinstance(evidence_bytes, (bytes, bytearray)):
        raise CustodyError("Rekor evidence must be supplied as raw bytes.")
    try:
        ev = json.loads(bytes(evidence_bytes).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise CustodyError(f"Rekor evidence is not valid UTF-8 JSON: {err}")
    if not isinstance(ev, dict) or ev.get("schema_version") != REKOR_EVIDENCE_SCHEMA_VERSION:
        raise CustodyError(f"Rekor evidence schema_version must be '{REKOR_EVIDENCE_SCHEMA_VERSION}'.")
    if ev.get("rekor_url") != REKOR_LOG_URL:
        raise CustodyError(f"Rekor evidence rekor_url must be '{REKOR_LOG_URL}', got '{ev.get('rekor_url')}'.")
    if ev.get("query_sha256") != manifest_sha256:
        raise CustodyError(
            f"Rekor evidence query_sha256 '{ev.get('query_sha256')}' does not equal manifest SHA-256 '{manifest_sha256}'."
        )
    if not _is_strict_int(ev.get("retrieved_at_unix")) or ev["retrieved_at_unix"] <= 0:
        raise CustodyError("Rekor evidence missing positive integer 'retrieved_at_unix'.")

    index_resp = ev.get("index_retrieve_response")
    if not isinstance(index_resp, list) or not index_resp:
        raise CustodyError("Rekor index search returned no entries for the manifest hash: no anchor exists.")
    index_keys = [_uuid_key(u) for u in index_resp]
    if len(set(index_keys)) != len(index_keys):
        raise CustodyError("Duplicate UUID in Rekor index search response.")

    raw_entries = ev.get("log_entries")
    if not isinstance(raw_entries, list):
        raise CustodyError("Rekor evidence missing 'log_entries' list.")

    parsed: dict[str, dict] = {}
    for raw in raw_entries:
        if not isinstance(raw, dict) or len(raw) != 1:
            raise CustodyError("Each archived Rekor log entry response must be an object with exactly one UUID key.")
        (uuid, body_obj), = raw.items()
        key = _uuid_key(uuid)
        if key in parsed:
            raise CustodyError(f"Rekor entry {key} archived more than once.")
        if not isinstance(body_obj, dict):
            raise CustodyError(f"Rekor entry {key} is not an object.")

        integrated_time = body_obj.get("integratedTime")
        log_index = body_obj.get("logIndex")
        if not _is_strict_int(integrated_time) or integrated_time <= 0:
            raise CustodyError(f"Rekor entry {key} has no positive integer integratedTime.")
        if not _is_strict_int(log_index) or log_index < 0:
            raise CustodyError(f"Rekor entry {key} has no non-negative integer logIndex.")
        verification = body_obj.get("verification")
        if not isinstance(verification, dict) or not verification.get("signedEntryTimestamp") \
                or not isinstance(verification.get("inclusionProof"), dict):
            raise CustodyError(f"Rekor entry {key} lacks signedEntryTimestamp/inclusionProof (not independently verifiable).")

        try:
            body = json.loads(base64.b64decode(body_obj.get("body", ""), validate=True).decode("utf-8"))
        except Exception as err:
            raise CustodyError(f"Rekor entry {key} body is not base64-encoded JSON: {err}")
        kind = body.get("kind") if isinstance(body, dict) else None
        if kind not in ALLOWED_REKOR_KINDS:
            raise CustodyError(f"Rekor entry {key} kind '{kind}' not in {sorted(ALLOWED_REKOR_KINDS)}.")
        h = ((body.get("spec") or {}).get("data") or {}).get("hash") or {}
        if h.get("algorithm") != "sha256":
            raise CustodyError(f"Rekor entry {key} artifact hash algorithm is '{h.get('algorithm')}', expected 'sha256'.")
        if str(h.get("value", "")).lower() != manifest_sha256:
            raise CustodyError(
                f"Rekor entry {key} records artifact hash '{h.get('value')}', not manifest SHA-256 '{manifest_sha256}'."
            )
        parsed[key] = {"uuid": key, "log_index": log_index, "integrated_time": integrated_time, "kind": kind}

    if set(parsed) != set(index_keys):
        missing = sorted(set(index_keys) - set(parsed))
        extra = sorted(set(parsed) - set(index_keys))
        raise CustodyError(
            f"Archived log entries do not match the index search result exactly (missing={missing}, unsearched={extra}). "
            f"Every entry returned for M must be archived so the earliest one can be determined."
        )

    for e in parsed.values():
        if e["integrated_time"] > ev["retrieved_at_unix"]:
            raise CustodyError(f"Rekor entry {e['uuid']} integratedTime is after retrieved_at_unix.")

    return sorted(parsed.values(), key=lambda e: (e["integrated_time"], e["log_index"]))


def validate_pool_custody_v2(
    manifest_bytes: bytes,
    pool_sha256: str,
    pool_size: int,
    pool_commitment: dict,
    pool_anchor: dict,
    anchor_evidence_bytes: bytes,
    expected_manifest_sha256: str | None = None,
) -> int:
    """
    Validates the complete v0.21 custody chain and returns T1.

      SHA256(manifest bytes) == expected carried-forward M
                             == commitment.manifest_sha256 == anchor.manifest_sha256
      manifest.bundle_files['POOL.tsv'] == SHA256(POOL.tsv bytes)
                             == commitment.pool_sha256 == anchor.pool_sha256
      canonical POOL row count == commitment.pool_size
      earliest Rekor entry for M:  uuid == anchor.anchor_proof_id,
                                   logIndex == anchor.anchor_log_index,
                                   integratedTime == anchor.verified_timestamp_unix
                                                  == commitment.published_at_unix  (= T1)
      SHA256(evidence bytes) == anchor.anchor_evidence_sha256
    """
    if expected_manifest_sha256 is None:
        expected_manifest_sha256 = CARRIED_FORWARD_MANIFEST_SHA256

    m = sha256_hex(bytes(manifest_bytes))
    if m != expected_manifest_sha256:
        raise CustodyError(
            f"Manifest SHA-256 '{m}' is not the carried-forward pool manifest '{expected_manifest_sha256}'. "
            f"Amendment v0.21 carries the run2 pool forward unchanged and admits no other pool."
        )
    manifest = parse_manifest(manifest_bytes)
    _require_hex64(pool_sha256, "computed POOL.tsv SHA-256")
    if manifest["bundle_files"]["POOL.tsv"] != pool_sha256:
        raise CustodyError(
            f"Manifest binds POOL.tsv '{manifest['bundle_files']['POOL.tsv']}', but supplied POOL.tsv hashes to '{pool_sha256}'."
        )

    # --- pool_commitment.json (v2) ---
    if not isinstance(pool_commitment, dict):
        raise CustodyError("pool_commitment must be an object.")
    _reject_retired(pool_commitment.get("schema_version"), "pool_commitment")
    if pool_commitment.get("schema_version") != POOL_COMMITMENT_SCHEMA_VERSION_V2:
        raise CustodyError(f"pool_commitment schema_version must be '{POOL_COMMITMENT_SCHEMA_VERSION_V2}'.")
    if set(pool_commitment) != COMMITMENT_V2_KEYS:
        raise CustodyError(f"pool_commitment keys must be exactly {sorted(COMMITMENT_V2_KEYS)}, got {sorted(pool_commitment)}.")
    if pool_commitment["manifest_sha256"] != m:
        raise CustodyError("pool_commitment.manifest_sha256 does not equal SHA-256 of the supplied manifest bytes.")
    if pool_commitment["pool_sha256"] != pool_sha256:
        raise CustodyError("pool_commitment.pool_sha256 does not equal SHA-256 of the supplied POOL.tsv bytes.")
    if not _is_strict_int(pool_commitment["pool_size"]) or pool_commitment["pool_size"] != pool_size:
        raise CustodyError(f"pool_commitment.pool_size {pool_commitment['pool_size']!r} != canonical POOL row count {pool_size}.")
    if not _is_strict_int(pool_commitment["published_at_unix"]):
        raise CustodyError("pool_commitment.published_at_unix must be an integer (T1 in Unix seconds).")

    # --- pool_anchor_receipt.json (v2) ---
    if not isinstance(pool_anchor, dict):
        raise CustodyError("pool_anchor must be an object.")
    _reject_retired(pool_anchor.get("schema_version"), "pool_anchor")
    if pool_anchor.get("schema_version") != POOL_ANCHOR_SCHEMA_VERSION_V2:
        raise CustodyError(f"pool_anchor schema_version must be '{POOL_ANCHOR_SCHEMA_VERSION_V2}'.")
    if set(pool_anchor) != ANCHOR_V2_KEYS:
        raise CustodyError(f"pool_anchor keys must be exactly {sorted(ANCHOR_V2_KEYS)}, got {sorted(pool_anchor)}.")
    if pool_anchor["anchor_type"] != ANCHOR_TYPE_REKOR:
        raise CustodyError(
            f"anchor_type '{pool_anchor['anchor_type']}' is not admissible; v0.21 admits only '{ANCHOR_TYPE_REKOR}' "
            f"(git_push is not externally verifiable; OpenTimestamps/RFC 3161 are not publicly searchable for earlier anchors)."
        )
    if pool_anchor["rekor_url"] != REKOR_LOG_URL:
        raise CustodyError(f"pool_anchor.rekor_url must be '{REKOR_LOG_URL}'.")
    if pool_anchor["verification_status"] != "ANCHOR_VERIFIED":
        raise CustodyError(f"pool_anchor verification_status must be 'ANCHOR_VERIFIED', got '{pool_anchor['verification_status']}'.")
    if not isinstance(pool_anchor["verifier"], str) or not pool_anchor["verifier"].strip():
        raise CustodyError("pool_anchor.verifier must name the external verification tool and version.")
    if pool_anchor["manifest_sha256"] != m:
        raise CustodyError("pool_anchor.manifest_sha256 does not equal SHA-256 of the supplied manifest bytes.")
    if pool_anchor["pool_sha256"] != pool_sha256:
        raise CustodyError("pool_anchor.pool_sha256 does not equal SHA-256 of the supplied POOL.tsv bytes.")
    if pool_anchor["anchor_evidence_sha256"] != sha256_hex(bytes(anchor_evidence_bytes)):
        raise CustodyError("pool_anchor.anchor_evidence_sha256 does not equal SHA-256 of the supplied Rekor evidence bytes.")

    entries = parse_rekor_evidence(anchor_evidence_bytes, m)
    earliest = entries[0]
    if _uuid_key(pool_anchor["anchor_proof_id"]) != earliest["uuid"]:
        raise CustodyError(
            f"pool_anchor.anchor_proof_id is not the EARLIEST Rekor entry for M (earliest is {earliest['uuid']} "
            f"at integratedTime {earliest['integrated_time']}). A later anchor cannot define T1."
        )
    if pool_anchor["anchor_log_index"] != earliest["log_index"] or not _is_strict_int(pool_anchor["anchor_log_index"]):
        raise CustodyError("pool_anchor.anchor_log_index does not match the earliest Rekor entry.")
    t1 = earliest["integrated_time"]
    if not _is_strict_int(pool_anchor["verified_timestamp_unix"]) or pool_anchor["verified_timestamp_unix"] != t1:
        raise CustodyError(
            f"pool_anchor.verified_timestamp_unix {pool_anchor['verified_timestamp_unix']!r} != T1 = {t1} (earliest integratedTime)."
        )
    if pool_commitment["published_at_unix"] != t1:
        raise CustodyError(
            f"pool_commitment.published_at_unix {pool_commitment['published_at_unix']} != T1 = {t1}. "
            f"published_at_unix is derived from the anchor, never chosen."
        )
    return t1


def derive_custody_records(
    manifest_bytes: bytes,
    pool_sha256: str,
    pool_size: int,
    anchor_evidence_bytes: bytes,
    verifier: str,
    expected_manifest_sha256: str | None = None,
) -> tuple[dict, dict]:
    """Derives pool_commitment (v2) and pool_anchor_receipt (v2) mechanically from the archived evidence, then self-validates."""
    m = sha256_hex(bytes(manifest_bytes))
    entries = parse_rekor_evidence(anchor_evidence_bytes, m)
    earliest = entries[0]
    commitment = {
        "schema_version": POOL_COMMITMENT_SCHEMA_VERSION_V2,
        "manifest_sha256": m,
        "pool_sha256": pool_sha256,
        "pool_size": pool_size,
        "published_at_unix": earliest["integrated_time"],
    }
    anchor = {
        "schema_version": POOL_ANCHOR_SCHEMA_VERSION_V2,
        "anchor_type": ANCHOR_TYPE_REKOR,
        "rekor_url": REKOR_LOG_URL,
        "manifest_sha256": m,
        "pool_sha256": pool_sha256,
        "anchor_proof_id": earliest["uuid"],
        "anchor_log_index": earliest["log_index"],
        "verified_timestamp_unix": earliest["integrated_time"],
        "anchor_evidence_sha256": sha256_hex(bytes(anchor_evidence_bytes)),
        "verifier": verifier,
        "verification_status": "ANCHOR_VERIFIED",
    }
    validate_pool_custody_v2(manifest_bytes, pool_sha256, pool_size, commitment, anchor,
                             anchor_evidence_bytes, expected_manifest_sha256)
    return commitment, anchor


def canonical_json_bytes(obj: dict) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8")
