#!/usr/bin/env python3
r"""
tools/pool_custody.py
Pre-randomness pool custody for representation-lifting-s1 (amendment v0.21, candidate r2).

Normative chain (PREREGISTRATION_v0.21 §3.5, §3.8):

    signed v0.21 freeze tag (object id F)   -- contains T_COMMIT_UNIX and RATIFIER_SSH_PUBLIC_KEY
        -> pool_commitment.json (v2) = anchor subject:
               {protocol, freeze_tag_object_id=F, manifest_sha256=M, pool_sha256=P,
                pool_size=N, published_at_unix=T_COMMIT_UNIX}      (canonical bytes)
        -> ratifier SSH signature over those exact bytes (namespace "file")
        -> ONE Rekor `rekord` entry for that signing event, identified by the UUID returned on upload
        -> T1 = integratedTime of THAT entry;  admissible iff T1 <= T_COMMIT_UNIX
        -> drand round r = compute_scheduled_round(T_COMMIT_UNIX)   (fixed before the freeze)

Why the round is derived from the precommitted T_COMMIT_UNIX and not from T1:
if the round were a function of the anchor time, the operator could anchor, wait for the round,
and, if unhappy, re-tag / re-subject / re-anchor ("anchor grinding"). Rekor's hash-index search
is best-effort and may be incomplete, so an abandoned earlier anchor cannot be proven absent.
With the round fixed in the signed freeze, the anchor decision is necessarily taken before that
round's randomness exists, and missing the deadline cannot be turned into a re-roll inside s1.

Why the subject contains the freeze tag object id: the subject cannot exist before the v0.21
freeze, so any pre-existing public anchor of the bare manifest hash M is irrelevant.

This module performs structural and binding validation of the archived raw Rekor API response.
Cryptographic verification (SET, inclusion proof, SSH signature) is performed externally with
`rekor-cli verify` and recorded in the receipt's `verifier` field (analysis boundary, §3.3).
No function here touches pool construction; the carried-forward pool is pinned.
"""

import base64
import hashlib
import json
import re
from typing import Any

POOL_COMMITMENT_SCHEMA_VERSION_V2 = "representation-lifting-pool-commitment/v2"
POOL_ANCHOR_SCHEMA_VERSION_V2 = "representation-lifting-pool-anchor/v2"
REKOR_ENTRY_EVIDENCE_SCHEMA_VERSION = "representation-lifting-rekor-entry-evidence/v1"
POOL_MANIFEST_SCHEMA_VERSION = "representation-lifting-pool-bundle-manifest/v1"
PROTOCOL_ID = "representation-lifting-s1/v0.21"

RETIRED_SCHEMA_VERSIONS = {
    "representation-lifting-pool-commitment/v1",
    "representation-lifting-pool-anchor/v1",
}

REKOR_LOG_URL = "https://rekor.sigstore.dev"
ANCHOR_TYPE_REKOR = "rekor"
ALLOWED_REKOR_KINDS = {"rekord"}          # SSH signatures are only representable as `rekord`
REQUIRED_SIGNATURE_FORMAT = "ssh"

# Carried-forward candidate pool (run2, frozen v0.20 builder f3c8978). v0.21 has no
# authority to regenerate or replace it; any other manifest is rejected.
CARRIED_FORWARD_MANIFEST_SHA256 = "aef332f69fb7bf70c0032dc05a383f8fea0085fecbd2ba22281c48ef4c36f7f6"
CARRIED_FORWARD_POOL_SHA256 = "398ddcb3d9e915edce681c0d59138950177d7eb096200795f927741fb9743212"
CARRIED_FORWARD_POOL_SIZE = 362

# Frozen v0.20 instrument identity (SHA-256 of file bytes at commit f3c8978).
FROZEN_BUILDER_SHA256 = "fccafe9e5a968098d99c7bd00015885c75be506c88854f220060862a8f7e3a65"
FROZEN_FILTER_SHA256 = "de48d2c28a735d0128e49a3a714708bf8fe1cf60cff20a70cff251649d921fdf"

# ---- FREEZE PARAMETERS: must be set in the candidate BEFORE the signed v0.21 tag. ----------
# T_COMMIT_UNIX: the Rekor entry must satisfy integratedTime <= T_COMMIT_UNIX; the drand round is
#   compute_scheduled_round(T_COMMIT_UNIX). Choose it far enough after the planned freeze to
#   anchor comfortably (hours, not minutes). A missed deadline is NOT_EVALUABLE_POOL_TIMESTAMP.
# RATIFIER_SSH_PUBLIC_KEY: "<type> <base64-blob>" of the key that signs the v0.21 freeze tag
#   (no comment). It is compared against Rekor's canonical key (ssh.MarshalAuthorizedKey form).
T_COMMIT_UNIX: int | None = 1790877600  # 2026-10-01 18:00:00 UTC; human-ratified by Ivan Nestorov
RATIFIER_SSH_PUBLIC_KEY: str | None = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAID0Yhb6zPoq9Kwnlx+pJqZ3UVh8pi7lyiStkajEo1R9m"
)  # fingerprint SHA256:5aVclA4mSj525gNohpxgBArgTo8qWvUbftMsGUs2TLw (Ivan Nestorov P10 ratifier)
# -------------------------------------------------------------------------------------------------

COMMITMENT_V2_KEYS = {"schema_version", "protocol", "freeze_tag_object_id", "manifest_sha256",
                      "pool_sha256", "pool_size", "published_at_unix"}
ANCHOR_V2_KEYS = {
    "schema_version", "anchor_type", "rekor_url", "subject_sha256", "manifest_sha256", "pool_sha256",
    "rekor_uuid", "rekor_log_index", "integrated_time_unix", "ratifier_ssh_public_key",
    "anchor_evidence_sha256", "verifier", "verification_status",
}

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")


class CustodyError(ValueError):
    """Raised on any violation of the v0.21 pre-randomness custody contract."""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(obj: dict) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8")


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


def ssh_key_identity(text: str) -> tuple[str, str]:
    """('ssh-ed25519', '<blob>') from an authorized_keys-style line; comment and whitespace ignored."""
    if not isinstance(text, str):
        raise CustodyError("SSH public key must be text.")
    parts = text.strip().split()
    if len(parts) < 2 or not parts[0].startswith(("ssh-", "ecdsa-", "sk-")):
        raise CustodyError(f"Not an OpenSSH public key line: {text[:40]!r}")
    try:
        base64.b64decode(parts[1], validate=True)
    except Exception:
        raise CustodyError("SSH public key blob is not valid base64.")
    return parts[0], parts[1]


def _reject_retired(schema: Any, what: str) -> None:
    if schema in RETIRED_SCHEMA_VERSIONS:
        raise CustodyError(
            f"{what} uses retired schema '{schema}'. The v0.20 anchor contract was superseded by "
            f"amendment v0.21; v1 custody artifacts are not admissible."
        )


def require_freeze_parameters(t_commit: int | None = None, ratifier_key: str | None = None) -> tuple[int, str]:
    t = T_COMMIT_UNIX if t_commit is None else t_commit
    k = RATIFIER_SSH_PUBLIC_KEY if ratifier_key is None else ratifier_key
    if not _is_strict_int(t) or t <= 0:
        raise CustodyError("Freeze parameter T_COMMIT_UNIX is not set; v0.21 is not freezable/usable.")
    if not isinstance(k, str):
        raise CustodyError("Freeze parameter RATIFIER_SSH_PUBLIC_KEY is not set; v0.21 is not freezable/usable.")
    ssh_key_identity(k)
    return t, k


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


def build_commitment(freeze_tag_object_id: str, manifest_bytes: bytes, pool_sha256: str, pool_size: int,
                     t_commit: int | None = None, expected_manifest_sha256: str | None = None) -> dict:
    """The anchor subject. Fully determined by the freeze tag, the pinned pool and T_COMMIT_UNIX."""
    t = T_COMMIT_UNIX if t_commit is None else t_commit
    if not _is_strict_int(t) or t <= 0:
        raise CustodyError("Freeze parameter T_COMMIT_UNIX is not set; v0.21 is not freezable/usable.")
    if not isinstance(freeze_tag_object_id, str) or not _HEX40.match(freeze_tag_object_id):
        raise CustodyError("freeze_tag_object_id must be a 40-hex git tag object id.")
    m = sha256_hex(bytes(manifest_bytes))
    exp = CARRIED_FORWARD_MANIFEST_SHA256 if expected_manifest_sha256 is None else expected_manifest_sha256
    if m != exp:
        raise CustodyError(f"Manifest SHA-256 '{m}' is not the carried-forward pool manifest '{exp}'.")
    manifest = parse_manifest(manifest_bytes)
    if manifest["bundle_files"]["POOL.tsv"] != pool_sha256:
        raise CustodyError("Manifest does not bind the supplied POOL.tsv.")
    return {
        "schema_version": POOL_COMMITMENT_SCHEMA_VERSION_V2,
        "protocol": PROTOCOL_ID,
        "freeze_tag_object_id": freeze_tag_object_id,
        "manifest_sha256": m,
        "pool_sha256": pool_sha256,
        "pool_size": pool_size,
        "published_at_unix": t,
    }


def parse_rekor_entry_evidence(evidence_bytes: bytes, subject_sha256: str, ratifier_key: str) -> dict:
    """
    Parses the archived raw response of GET /api/v1/log/entries/{uuid} for the ONE entry created
    by uploading the ratifier's signature over the subject. No index search is used.

    Evidence schema (representation-lifting-rekor-entry-evidence/v1):
      {"schema_version": ..., "rekor_url": "https://rekor.sigstore.dev",
       "requested_uuid": "<uuid returned by rekor-cli upload>",
       "retrieved_at_unix": <int, informational only>,
       "log_entry": <raw JSON response: {uuid: {body, integratedTime, logID, logIndex, verification}}>}
    Returns {'uuid','log_index','integrated_time'}.
    """
    if not isinstance(evidence_bytes, (bytes, bytearray)):
        raise CustodyError("Rekor evidence must be supplied as raw bytes.")
    try:
        ev = json.loads(bytes(evidence_bytes).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise CustodyError(f"Rekor evidence is not valid UTF-8 JSON: {err}")
    if not isinstance(ev, dict) or ev.get("schema_version") != REKOR_ENTRY_EVIDENCE_SCHEMA_VERSION:
        raise CustodyError(f"Rekor evidence schema_version must be '{REKOR_ENTRY_EVIDENCE_SCHEMA_VERSION}'.")
    if ev.get("rekor_url") != REKOR_LOG_URL:
        raise CustodyError(f"Rekor evidence rekor_url must be '{REKOR_LOG_URL}', got '{ev.get('rekor_url')}'.")
    requested = _uuid_key(ev.get("requested_uuid"))
    raw = ev.get("log_entry")
    if not isinstance(raw, dict) or len(raw) != 1:
        raise CustodyError("log_entry must be the raw Rekor response: an object with exactly one UUID key.")
    (uuid, obj), = raw.items()
    key = _uuid_key(uuid)
    if key != requested:
        raise CustodyError(f"Archived entry {key} is not the requested upload UUID {requested}.")
    if not isinstance(obj, dict):
        raise CustodyError("Rekor entry is not an object.")

    t = obj.get("integratedTime")
    idx = obj.get("logIndex")
    if not _is_strict_int(t) or t <= 0:
        raise CustodyError("Rekor entry has no positive integer integratedTime.")
    if not _is_strict_int(idx) or idx < 0:
        raise CustodyError("Rekor entry has no non-negative integer logIndex.")

    ver = obj.get("verification")
    if not isinstance(ver, dict) or not isinstance(ver.get("signedEntryTimestamp"), str) or not ver["signedEntryTimestamp"]:
        raise CustodyError("Rekor entry lacks a signedEntryTimestamp.")
    proof = ver.get("inclusionProof")
    if not isinstance(proof, dict):
        raise CustodyError("Rekor entry lacks an inclusionProof.")
    proof_idx = proof.get("logIndex")
    if not _is_strict_int(proof_idx) or proof_idx < 0:
        raise CustodyError("inclusionProof.logIndex must be a non-negative integer.")
    if not _is_strict_int(proof.get("treeSize")) or proof["treeSize"] <= proof_idx:
        raise CustodyError("inclusionProof.treeSize must be greater than inclusionProof.logIndex.")
    if not isinstance(proof.get("rootHash"), str) or not _HEX64.match(proof["rootHash"].lower()):
        raise CustodyError("inclusionProof.rootHash must be a 64-hex SHA-256 value.")
    if not isinstance(proof.get("hashes"), list):
        raise CustodyError("inclusionProof.hashes must be a list.")

    try:
        body = json.loads(base64.b64decode(obj.get("body", ""), validate=True).decode("utf-8"))
    except Exception as err:
        raise CustodyError(f"Rekor entry body is not base64-encoded JSON: {err}")
    kind = body.get("kind") if isinstance(body, dict) else None
    if kind not in ALLOWED_REKOR_KINDS:
        raise CustodyError(f"Rekor entry kind '{kind}' not admissible; required {sorted(ALLOWED_REKOR_KINDS)}.")
    spec = body.get("spec") or {}
    h = (spec.get("data") or {}).get("hash") or {}
    if h.get("algorithm") != "sha256" or str(h.get("value", "")).lower() != subject_sha256:
        raise CustodyError(
            f"Rekor entry artifact hash {h.get('algorithm')}:{h.get('value')} is not sha256:{subject_sha256} (the anchor subject)."
        )
    sig = spec.get("signature") or {}
    if sig.get("format") != REQUIRED_SIGNATURE_FORMAT:
        raise CustodyError(f"Rekor entry signature format '{sig.get('format')}' is not '{REQUIRED_SIGNATURE_FORMAT}'.")
    try:
        entry_key = base64.b64decode((sig.get("publicKey") or {}).get("content", ""), validate=True).decode("utf-8")
    except Exception:
        raise CustodyError("Rekor entry public key content is not base64 text.")
    if ssh_key_identity(entry_key) != ssh_key_identity(ratifier_key):
        raise CustodyError("Rekor entry was not signed with the pinned ratifier SSH key.")
    if not sig.get("content"):
        raise CustodyError("Rekor entry carries no signature content.")
    return {"uuid": key, "log_index": idx, "integrated_time": t}


def validate_pool_custody_v2(
    manifest_bytes: bytes,
    pool_sha256: str,
    pool_size: int,
    pool_commitment: dict,
    pool_anchor: dict,
    anchor_evidence_bytes: bytes,
    expected_manifest_sha256: str | None = None,
    t_commit: int | None = None,
    ratifier_key: str | None = None,
) -> int:
    """
    Validates the complete v0.21 custody chain. Returns T1 (the entry's integratedTime).

      SHA256(manifest) == carried-forward M == commitment.manifest_sha256 == anchor.manifest_sha256
      manifest.bundle_files['POOL.tsv'] == SHA256(POOL.tsv) == commitment.pool_sha256 == anchor.pool_sha256
      canonical POOL row count == commitment.pool_size
      commitment.published_at_unix == T_COMMIT_UNIX ; commitment.protocol == v0.21
      SHA256(canonical commitment bytes) == anchor.subject_sha256 == Rekor entry artifact hash
      Rekor entry: kind rekord, format ssh, key == pinned ratifier key, uuid == anchor.rekor_uuid,
                   logIndex == anchor.rekor_log_index, integratedTime == anchor.integrated_time_unix
      T1 <= T_COMMIT_UNIX
    """
    t_c, key = require_freeze_parameters(t_commit, ratifier_key)
    exp = CARRIED_FORWARD_MANIFEST_SHA256 if expected_manifest_sha256 is None else expected_manifest_sha256

    m = sha256_hex(bytes(manifest_bytes))
    if m != exp:
        raise CustodyError(
            f"Manifest SHA-256 '{m}' is not the carried-forward pool manifest '{exp}'. "
            f"Amendment v0.21 carries the run2 pool forward unchanged and admits no other pool."
        )
    manifest = parse_manifest(manifest_bytes)
    _require_hex64(pool_sha256, "computed POOL.tsv SHA-256")
    if manifest["bundle_files"]["POOL.tsv"] != pool_sha256:
        raise CustodyError(
            f"Manifest binds POOL.tsv '{manifest['bundle_files']['POOL.tsv']}', but supplied POOL.tsv hashes to '{pool_sha256}'."
        )

    # --- pool_commitment.json (v2) = anchor subject ---
    if not isinstance(pool_commitment, dict):
        raise CustodyError("pool_commitment must be an object.")
    _reject_retired(pool_commitment.get("schema_version"), "pool_commitment")
    if pool_commitment.get("schema_version") != POOL_COMMITMENT_SCHEMA_VERSION_V2:
        raise CustodyError(f"pool_commitment schema_version must be '{POOL_COMMITMENT_SCHEMA_VERSION_V2}'.")
    if set(pool_commitment) != COMMITMENT_V2_KEYS:
        raise CustodyError(f"pool_commitment keys must be exactly {sorted(COMMITMENT_V2_KEYS)}, got {sorted(pool_commitment)}.")
    if pool_commitment["protocol"] != PROTOCOL_ID:
        raise CustodyError(f"pool_commitment.protocol must be '{PROTOCOL_ID}'.")
    if not isinstance(pool_commitment["freeze_tag_object_id"], str) or not _HEX40.match(pool_commitment["freeze_tag_object_id"]):
        raise CustodyError("pool_commitment.freeze_tag_object_id must be a 40-hex git tag object id.")
    if pool_commitment["manifest_sha256"] != m:
        raise CustodyError("pool_commitment.manifest_sha256 does not equal SHA-256 of the supplied manifest bytes.")
    if pool_commitment["pool_sha256"] != pool_sha256:
        raise CustodyError("pool_commitment.pool_sha256 does not equal SHA-256 of the supplied POOL.tsv bytes.")
    if not _is_strict_int(pool_commitment["pool_size"]) or pool_commitment["pool_size"] != pool_size:
        raise CustodyError(f"pool_commitment.pool_size {pool_commitment['pool_size']!r} != canonical POOL row count {pool_size}.")
    if not _is_strict_int(pool_commitment["published_at_unix"]) or pool_commitment["published_at_unix"] != t_c:
        raise CustodyError(
            f"pool_commitment.published_at_unix {pool_commitment['published_at_unix']!r} != frozen T_COMMIT_UNIX {t_c}. "
            f"The round reference time is precommitted in the signed freeze, never chosen at anchoring."
        )
    subject = sha256_hex(canonical_json_bytes(pool_commitment))

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
            f"anchor_type '{pool_anchor['anchor_type']}' is not admissible; v0.21 admits only '{ANCHOR_TYPE_REKOR}'."
        )
    if pool_anchor["rekor_url"] != REKOR_LOG_URL:
        raise CustodyError(f"pool_anchor.rekor_url must be '{REKOR_LOG_URL}'.")
    if pool_anchor["verification_status"] != "ANCHOR_VERIFIED":
        raise CustodyError(f"pool_anchor verification_status must be 'ANCHOR_VERIFIED', got '{pool_anchor['verification_status']}'.")
    if not isinstance(pool_anchor["verifier"], str) or not pool_anchor["verifier"].strip():
        raise CustodyError("pool_anchor.verifier must name the external verification tool and version.")
    if pool_anchor["subject_sha256"] != subject:
        raise CustodyError("pool_anchor.subject_sha256 does not equal SHA-256 of the canonical pool_commitment bytes.")
    if pool_anchor["manifest_sha256"] != m:
        raise CustodyError("pool_anchor.manifest_sha256 does not equal SHA-256 of the supplied manifest bytes.")
    if pool_anchor["pool_sha256"] != pool_sha256:
        raise CustodyError("pool_anchor.pool_sha256 does not equal SHA-256 of the supplied POOL.tsv bytes.")
    if not isinstance(pool_anchor["ratifier_ssh_public_key"], str) or \
            ssh_key_identity(pool_anchor["ratifier_ssh_public_key"]) != ssh_key_identity(key):
        raise CustodyError("pool_anchor.ratifier_ssh_public_key is not the pinned ratifier key.")
    if pool_anchor["anchor_evidence_sha256"] != sha256_hex(bytes(anchor_evidence_bytes)):
        raise CustodyError("pool_anchor.anchor_evidence_sha256 does not equal SHA-256 of the supplied Rekor evidence bytes.")

    entry = parse_rekor_entry_evidence(anchor_evidence_bytes, subject, key)
    if _uuid_key(pool_anchor["rekor_uuid"]) != entry["uuid"]:
        raise CustodyError("pool_anchor.rekor_uuid does not identify the archived Rekor entry.")
    if not _is_strict_int(pool_anchor["rekor_log_index"]) or pool_anchor["rekor_log_index"] != entry["log_index"]:
        raise CustodyError("pool_anchor.rekor_log_index does not match the archived Rekor entry.")
    t1 = entry["integrated_time"]
    if not _is_strict_int(pool_anchor["integrated_time_unix"]) or pool_anchor["integrated_time_unix"] != t1:
        raise CustodyError(f"pool_anchor.integrated_time_unix {pool_anchor['integrated_time_unix']!r} != entry integratedTime {t1}.")
    if t1 > t_c:
        raise CustodyError(
            f"Anchor integratedTime {t1} is after the frozen deadline T_COMMIT_UNIX {t_c}: the pool was not "
            f"externally anchored before the precommitted reference time. H2 is NOT_EVALUABLE_POOL_TIMESTAMP; "
            f"no re-roll is admissible within s1."
        )
    return t1


def derive_anchor_receipt(pool_commitment: dict, anchor_evidence_bytes: bytes, verifier: str,
                          manifest_bytes: bytes, pool_sha256: str, pool_size: int,
                          expected_manifest_sha256: str | None = None,
                          t_commit: int | None = None, ratifier_key: str | None = None) -> dict:
    """Derives pool_anchor_receipt.json (v2) from the archived entry, then self-validates the full chain."""
    _, key = require_freeze_parameters(t_commit, ratifier_key)
    subject = sha256_hex(canonical_json_bytes(pool_commitment))
    entry = parse_rekor_entry_evidence(anchor_evidence_bytes, subject, key)
    anchor = {
        "schema_version": POOL_ANCHOR_SCHEMA_VERSION_V2,
        "anchor_type": ANCHOR_TYPE_REKOR,
        "rekor_url": REKOR_LOG_URL,
        "subject_sha256": subject,
        "manifest_sha256": pool_commitment.get("manifest_sha256"),
        "pool_sha256": pool_commitment.get("pool_sha256"),
        "rekor_uuid": entry["uuid"],
        "rekor_log_index": entry["log_index"],
        "integrated_time_unix": entry["integrated_time"],
        "ratifier_ssh_public_key": " ".join(ssh_key_identity(key)),
        "anchor_evidence_sha256": sha256_hex(bytes(anchor_evidence_bytes)),
        "verifier": verifier,
        "verification_status": "ANCHOR_VERIFIED",
    }
    validate_pool_custody_v2(manifest_bytes, pool_sha256, pool_size, pool_commitment, anchor,
                             anchor_evidence_bytes, expected_manifest_sha256, t_commit, ratifier_key)
    return anchor
