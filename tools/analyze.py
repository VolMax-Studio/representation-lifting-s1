#!/usr/bin/env python3
"""
tools/analyze.py
Deterministic Analysis Custody and Outcome Adjudication for representation-lifting-s1.

Pre-frozen analysis rules (v0.14):
1. Primary Categorical Completion Outcome:
   O_completion ∈ {BOTH, L-ONLY, D-ONLY, NEITHER, NOT_EVALUABLE_INFRA}
   - Evaluated from verified final statuses of Direct and Lifted branches.
   - Any transport/infrastructure failure classifies strictly as NOT_EVALUABLE_INFRA.
2. Formalization Footprint Differential:
   ΔW = W_L - W_D
   - Calculated STRICTLY conditional on O_completion == BOTH.
   - If O_completion != BOTH, ΔW is undefined (None).
3. Calibration Family Hypothesis (H1):
   - Per-family verdict:
     PASS ⇔ (2 * Δ_L^(2) <= Δ_D^(2)) ∧ (W_L(T1 + T2) < W_D(T1 + T2))
   - Proof failure or incomplete data ⇔ NOT_EVALUABLE.
   - Transport/infrastructure failure ⇔ NOT_EVALUABLE_INFRA.
   - Any condition failure ⇔ REJECT.
   - Completeness & Aggregation:
     Each model MUST evaluate all 3 predeclared families: {fibonacci, pell, roots_of_unity}.
     If any family is missing for a model, H1 for that model is NOT_EVALUABLE.
     H1_primary = PASS ⇔ all 3 families PASS.
     Any family REJECT ⇔ REJECT.
     No REJECT but any NOT_EVALUABLE ⇔ NOT_EVALUABLE.
     Replication model receives identical independent evaluation and never overrides primary.
4. Mandatory Negative Control Arm Decision Matrix (H0):
   - If control receipt is missing ⇔ CONTROL_MISSING. Veto is ACTIVE; H1 and H2 are invalidated.
   - D-ONLY ⇔ CONTROL_PASS
   - BOTH & (W_D < W_L) ⇔ CONTROL_PASS
   - L-ONLY ⇔ COMPROMISED
   - BOTH & (W_L <= W_D) ⇔ COMPROMISED
   - NEITHER ⇔ CONTROL_INCONCLUSIVE
   - Transport/infrastructure failure ⇔ CONTROL_NOT_EVALUABLE_INFRA
   - COMPROMISED completely invalidates methodological conclusions of H1 and H2.
5. Blind Transfer Arm (H2):
   - Mechanical descriptive summary: count of LIFT_FOUND vs LIFT_NOT_FOUND,
     distribution of O_completion across 3 cases, and ΔW conditional on BOTH.
   - Zero population extrapolation.
6. Model Role Mapping:
   - Evaluated models are mapped to primary and replication roles via frozen tools/executor_config.json.
   - Receipts missing model_id fail closed immediately (no silent fallback).
"""

import sys
import os
import json
import argparse
import hashlib
from typing import Any

try:
    from select_indices import select_indices
    from drand_schedule import compute_scheduled_round, QUICKNET_CHAIN_HASH, QUICKNET_GROUP_HASH
    import pool_custody
except ImportError:
    from tools.select_indices import select_indices
    from tools.drand_schedule import compute_scheduled_round, QUICKNET_CHAIN_HASH, QUICKNET_GROUP_HASH
    from tools import pool_custody

SCHEMA_VERSION = "representation-lifting-execution-receipt/v1"
CONFIG_SCHEMA_VERSION = "representation-lifting-executor-config/v1"
SELECTION_SCHEMA_VERSION = "representation-lifting-selection/v1"
# Amendment v0.21: pre-randomness custody schemas v2 (v1 retired; see tools/pool_custody.py).
POOL_COMMITMENT_SCHEMA_VERSION = pool_custody.POOL_COMMITMENT_SCHEMA_VERSION_V2
POOL_ANCHOR_SCHEMA_VERSION = pool_custody.POOL_ANCHOR_SCHEMA_VERSION_V2
BEACON_VERIFICATION_SCHEMA_VERSION = "representation-lifting-beacon-verification/v1"
DRAND_QUICKNET_PUBLIC_KEY_HEX = "83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a"
DRAND_QUICKNET_SCHEME_ID = "bls-unchained-g1-rfc9380"
DRAND_QUICKNET_GROUP_HASH = QUICKNET_GROUP_HASH
REQUIRED_CALIBRATION_FAMILIES = {"fibonacci", "pell", "roots_of_unity"}

class InputContractError(ValueError):
    """Raised when study inputs violate the frozen pre-execution contract."""
    pass

def load_executor_config(config_path: str | None = None) -> dict:
    """
    Loads tools/executor_config.json as the sole source of truth for model bindings.
    Fails closed if the file does not exist, is invalid JSON, or violates schema.
    """
    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), "executor_config.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Mandatory executor configuration file not found at: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    if not isinstance(cfg, dict):
        raise InputContractError("Executor configuration must be a valid JSON object.")
    if cfg.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise InputContractError(f"Config schema version mismatch: expected '{CONFIG_SCHEMA_VERSION}', got '{cfg.get('schema_version')}'")
    primary_id = cfg.get("primary_model_id")
    replication_id = cfg.get("replication_model_id")
    if not primary_id or not replication_id:
        raise InputContractError("Config missing mandatory 'primary_model_id' or 'replication_model_id'.")
    if primary_id == replication_id:
        raise InputContractError("Primary and replication model IDs must be distinct.")
    return cfg

def parse_pool_tsv(pool_input: str | bytes) -> tuple[bytes, list[str]]:
    """
    Parses POOL.tsv into raw canonical bytes and an indexed list of case_ids.
    - If pool_input is str, encodes to utf-8.
    - Strips optional header row if the first column is named 'case_id', 'id', 'proofnet_id', etc.
    - Returns (pool_bytes, case_ids).
    """
    if isinstance(pool_input, str):
        pool_bytes = pool_input.encode("utf-8")
        text = pool_input
    elif isinstance(pool_input, bytes):
        pool_bytes = pool_input
        text = pool_input.decode("utf-8")
    else:
        raise InputContractError("POOL.tsv content must be str or bytes.")

    lines = [line.strip() for line in text.splitlines()]
    non_empty_lines = [line for line in lines if line]
    if not non_empty_lines:
        raise InputContractError("POOL.tsv is empty.")

    first_cols = [c.strip().lower() for c in non_empty_lines[0].split("\t")]
    if first_cols[0] in ("case_id", "id", "proofnet_id", "identifier", "name"):
        data_lines = non_empty_lines[1:]
    else:
        data_lines = non_empty_lines

    if not data_lines:
        raise InputContractError("POOL.tsv contains no data rows.")

    case_ids = []
    seen_case_ids = set()
    for line_idx, line in enumerate(data_lines, start=1):
        cid = line.split("\t")[0].strip()
        if not cid:
            raise InputContractError(f"Found empty case_id in POOL.tsv data row {line_idx}.")
        if cid in seen_case_ids:
            raise InputContractError(f"Duplicate case_id '{cid}' detected in POOL.tsv data row {line_idx}.")
        seen_case_ids.add(cid)
        case_ids.append(cid)

    return pool_bytes, case_ids

def validate_selection(
    pool_tsv: str | bytes,
    pool_commitment: dict,
    selection_record: dict,
    pool_anchor: dict | None = None,
    beacon_verification: dict | None = None,
    pool_manifest: bytes | None = None,
    pool_anchor_evidence: bytes | None = None
) -> list[dict]:
    """
    Strict mechanical validation and recomputation of the drand blind selection custody chain:
    POOL bytes -> pool SHA-256 -> pool size -> scheduled round -> beacon signature -> R -> indices -> case_ids.

    Validates external anchors when provided:
    - pool_anchor (v0.21): requires the raw pool_bundle_manifest.json bytes and the archived raw
      Rekor evidence; validates the full chain manifest -> POOL.tsv -> commitment/v2 -> anchor/v2 ->
      earliest Rekor entry, with published_at_unix == verified_timestamp_unix == T1
      (tools/pool_custody.validate_pool_custody_v2).
    - beacon_verification: verifies external BLS verification status, chain hash, round, signature, and scheme.

    Returns the authoritative list of 3 selected items: [{'index': idx, 'case_id': cid}, ...]
    Raises InputContractError upon ANY contract violation, hash mismatch, or tampering.
    """
    if not isinstance(pool_commitment, dict):
        raise InputContractError("pool_commitment must be a dictionary.")
    if pool_commitment.get("schema_version") in pool_custody.RETIRED_SCHEMA_VERSIONS:
        raise InputContractError(
            f"pool_commitment uses retired schema '{pool_commitment.get('schema_version')}' (superseded by amendment v0.21)."
        )
    if pool_commitment.get("schema_version") != POOL_COMMITMENT_SCHEMA_VERSION:
        raise InputContractError(
            f"Pool commitment schema_version mismatch: expected '{POOL_COMMITMENT_SCHEMA_VERSION}', got '{pool_commitment.get('schema_version')}'"
        )

    pool_bytes, pool_case_ids = parse_pool_tsv(pool_tsv)
    computed_pool_hash = hashlib.sha256(pool_bytes).hexdigest()
    committed_pool_hash = pool_commitment.get("pool_sha256")
    if computed_pool_hash != committed_pool_hash:
        raise InputContractError(
            f"POOL.tsv SHA-256 mismatch: computed '{computed_pool_hash}', but pool_commitment committed '{committed_pool_hash}'."
        )

    pool_size = pool_commitment.get("pool_size")
    if not isinstance(pool_size, int) or pool_size <= 0:
        raise InputContractError(f"Invalid pool_size in pool_commitment: {pool_size}")
    if len(pool_case_ids) != pool_size:
        raise InputContractError(
            f"Pool size mismatch: pool_commitment specifies pool_size={pool_size}, but POOL.tsv contains {len(pool_case_ids)} canonical data rows."
        )

    pub_time = pool_commitment.get("published_at_unix")
    if not isinstance(pub_time, int) or isinstance(pub_time, bool) or pub_time <= 0:
        raise InputContractError("pool_commitment missing valid positive integer 'published_at_unix' timestamp (v0.21: T1).")
    pub_time_int = pub_time

    # v0.21: manifest binding is checked whenever the manifest is supplied; with an anchor it is mandatory.
    if pool_anchor is not None and (pool_manifest is None or pool_anchor_evidence is None):
        raise InputContractError(
            "pool_anchor supplied without pool_manifest bytes and pool_anchor_evidence bytes; "
            "the v0.21 anchor contract cannot be validated from receipt fields alone."
        )
    if pool_manifest is not None:
        if pool_commitment.get("manifest_sha256") != hashlib.sha256(bytes(pool_manifest)).hexdigest():
            raise InputContractError("pool_commitment.manifest_sha256 does not equal SHA-256 of the supplied manifest bytes.")
        try:
            manifest_obj = pool_custody.parse_manifest(pool_manifest)
        except pool_custody.CustodyError as err:
            raise InputContractError(f"Pool custody violation: {err}")
        if manifest_obj["bundle_files"]["POOL.tsv"] != computed_pool_hash:
            raise InputContractError("Manifest bundle_files['POOL.tsv'] does not equal SHA-256 of the supplied POOL.tsv bytes.")
    if pool_anchor is not None:
        try:
            t1 = pool_custody.validate_pool_custody_v2(
                pool_manifest, computed_pool_hash, len(pool_case_ids),
                pool_commitment, pool_anchor, pool_anchor_evidence,
            )
        except pool_custody.CustodyError as err:
            raise InputContractError(f"Pool custody violation: {err}")
        if t1 != pub_time_int:
            raise InputContractError(f"Custody T1 {t1} != published_at_unix {pub_time_int}.")

    # Validate selection_record
    if not isinstance(selection_record, dict):
        raise InputContractError("selection_record must be a dictionary.")
    if selection_record.get("schema_version") != SELECTION_SCHEMA_VERSION:
        raise InputContractError(
            f"Selection record schema_version mismatch: expected '{SELECTION_SCHEMA_VERSION}', got '{selection_record.get('schema_version')}'"
        )

    chain_hash = selection_record.get("quicknet_chain_hash")
    if chain_hash != QUICKNET_CHAIN_HASH:
        raise InputContractError(
            f"Invalid quicknet_chain_hash in selection_record: expected '{QUICKNET_CHAIN_HASH}', got '{chain_hash}'"
        )

    sig_hex = selection_record.get("signature_hex")
    if not sig_hex or not isinstance(sig_hex, str):
        raise InputContractError("selection_record missing valid string 'signature_hex'.")
    try:
        sig_bytes = bytes.fromhex(sig_hex)
    except ValueError:
        raise InputContractError("Invalid hex string in 'signature_hex'.")

    # Drand Quicknet BLS signature sanity check: G1 point is strictly 48 bytes (96 hex chars)
    if len(sig_bytes) != 48:
        raise InputContractError(
            f"Quicknet BLS signature length violation: expected exactly 48 bytes (G1, 96 hex characters), got {len(sig_bytes)} bytes."
        )

    rand_hex = selection_record.get("randomness_hex")
    if not rand_hex or not isinstance(rand_hex, str):
        raise InputContractError("selection_record missing valid string 'randomness_hex'.")

    # Recompute R = SHA256(signature) as per drand quicknet specification
    computed_rand_bytes = hashlib.sha256(sig_bytes).digest()
    computed_rand_hex = computed_rand_bytes.hex()
    if computed_rand_hex.lower() != rand_hex.strip().lower():
        raise InputContractError(
            f"Randomness integrity violation: SHA256(signature_hex) is '{computed_rand_hex}', but selection_record recorded randomness_hex='{rand_hex}'."
        )

    expected_round = compute_scheduled_round(pub_time_int)
    recorded_round = selection_record.get("round")
    if recorded_round != expected_round:
        raise InputContractError(
            f"Drand scheduled round mismatch: computed round {expected_round} from published_at_unix={pub_time_int}, but selection_record recorded round {recorded_round}."
        )

    recomputed_indices = select_indices(computed_rand_bytes, pool_size, count=3)
    if len(recomputed_indices) != 3:
        raise InputContractError(f"select_indices failed to produce exactly 3 indices: {recomputed_indices}")

    recomputed_selected = [
        {"index": idx, "case_id": pool_case_ids[idx]}
        for idx in recomputed_indices
    ]

    rec_selected = selection_record.get("selected")
    if not isinstance(rec_selected, list):
        raise InputContractError("selection_record missing 'selected' list.")
    if len(rec_selected) != 3:
        raise InputContractError(f"selection_record['selected'] must contain exactly 3 cases, got {len(rec_selected)}.")

    rec_indices = []
    rec_case_ids = []
    for item in rec_selected:
        if not isinstance(item, dict):
            raise InputContractError("Each item in selection_record['selected'] must be an object.")
        idx = item.get("index")
        cid = item.get("case_id")
        if not isinstance(idx, int) or not isinstance(cid, str):
            raise InputContractError(f"Malformed item in selection_record['selected']: {item}")
        rec_indices.append(idx)
        rec_case_ids.append(cid)

    if len(set(rec_indices)) != 3:
        raise InputContractError(f"Duplicate index found in selection_record['selected']: {rec_indices}")
    if len(set(rec_case_ids)) != 3:
        raise InputContractError(f"Duplicate case_id found in selection_record['selected']: {rec_case_ids}")

    expected_indices = [item["index"] for item in recomputed_selected]
    expected_case_ids = [item["case_id"] for item in recomputed_selected]

    if rec_indices != expected_indices:
        raise InputContractError(
            f"Selected indices mismatch: recomputed indices {expected_indices} do not match recorded indices {rec_indices}."
        )
    if rec_case_ids != expected_case_ids:
        raise InputContractError(
            f"Selected case_ids mismatch: recomputed case_ids {expected_case_ids} do not match recorded case_ids {rec_case_ids}."
        )

    # External pool anchor receipt (v0.21) is validated above, before the round is derived
    # from published_at_unix, so the round can only be computed from an anchor-bound T1.

    # Validate external beacon verification receipt if provided
    if beacon_verification is not None:
        if not isinstance(beacon_verification, dict):
            raise InputContractError("beacon_verification must be a dictionary.")
        if beacon_verification.get("schema_version") != BEACON_VERIFICATION_SCHEMA_VERSION:
            raise InputContractError(
                f"Beacon verification schema_version mismatch: expected '{BEACON_VERIFICATION_SCHEMA_VERSION}', got '{beacon_verification.get('schema_version')}'"
            )
        if beacon_verification.get("verification_status") != "BLS_VERIFIED":
            raise InputContractError(
                f"Beacon verification verification_status must be 'BLS_VERIFIED', got '{beacon_verification.get('verification_status')}'"
            )
        if beacon_verification.get("quicknet_chain_hash") != QUICKNET_CHAIN_HASH:
            raise InputContractError(
                f"Beacon verification quicknet_chain_hash mismatch: expected '{QUICKNET_CHAIN_HASH}', got '{beacon_verification.get('quicknet_chain_hash')}'"
            )
        if beacon_verification.get("round") != recorded_round:
            raise InputContractError(
                f"Beacon verification round mismatch: expected {recorded_round}, got {beacon_verification.get('round')}."
            )
        if beacon_verification.get("signature_hex") != sig_hex:
            raise InputContractError(
                "Beacon verification signature_hex does not match selection_record signature_hex."
            )
        if beacon_verification.get("scheme_id") != DRAND_QUICKNET_SCHEME_ID:
            raise InputContractError(
                f"Beacon verification scheme_id mismatch: expected '{DRAND_QUICKNET_SCHEME_ID}', got '{beacon_verification.get('scheme_id')}'"
            )
        pk_hex = beacon_verification.get("public_key_hex")
        if not pk_hex or not isinstance(pk_hex, str):
            raise InputContractError("Beacon verification missing valid string 'public_key_hex'.")
        try:
            pk_bytes = bytes.fromhex(pk_hex)
        except ValueError:
            raise InputContractError("Invalid hex string in beacon verification 'public_key_hex'.")
        if len(pk_bytes) != 96:
            raise InputContractError(
                f"Quicknet public key length violation: expected exactly 96 bytes (G2, 192 hex characters), got {len(pk_bytes)} bytes."
            )
        if pk_hex.strip().lower() != DRAND_QUICKNET_PUBLIC_KEY_HEX.lower():
            raise InputContractError(
                f"Beacon verification public_key_hex mismatch: expected '{DRAND_QUICKNET_PUBLIC_KEY_HEX}', got '{pk_hex}'."
            )

    return recomputed_selected

def validate_study_inputs(
    config: dict,
    control_receipts: list[dict] | None = None,
    calibration_receipts: list[dict] | None = None,
    blind_receipts: list[dict] | None = None,
    selection_record: dict | None = None,
    pool_commitment: dict | None = None,
    pool_tsv: str | bytes | None = None,
    pool_anchor: dict | None = None,
    beacon_verification: dict | None = None,
    pool_manifest: bytes | None = None,
    pool_anchor_evidence: bytes | None = None
) -> list[dict] | None:
    """
    Strictly validates input contract before any analysis:
    - Config matches schema and defines distinct primary and replication models.
    - Every receipt has schema_version == SCHEMA_VERSION.
    - Every receipt has a valid receipt_type matching its arm.
    - Every receipt has a model_id belonging to {primary_model_id, replication_model_id}. Unregistered model raises InputContractError.
    - No duplicates: duplicate (model_id) in control, duplicate (model_id, family_name) in calibration, or duplicate (model_id, case_id) in blind raises InputContractError.
    - In calibration: only known families in REQUIRED_CALIBRATION_FAMILIES are permitted.
    - If selection custody is provided:
      - selection_record, pool_commitment, and pool_tsv must all be provided together.
      - validate_selection fully reproduces and validates the custody chain and external anchors.
      - Any blind receipt with a case_id NOT in the selection record raises InputContractError.
    Returns the validated list of selected items, or None if no selection custody was provided.
    """
    if not isinstance(config, dict):
        raise InputContractError("Config must be a dictionary.")
    if config.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise InputContractError(f"Config schema version mismatch: expected '{CONFIG_SCHEMA_VERSION}', got '{config.get('schema_version')}'")
    primary_id = config.get("primary_model_id")
    replication_id = config.get("replication_model_id")
    if not primary_id or not replication_id:
        raise InputContractError("Config missing mandatory 'primary_model_id' or 'replication_model_id'.")
    registered_models = {primary_id, replication_id}

    # 1. Negative control receipts validation
    seen_ctrl_models = set()
    for r in (control_receipts or []):
        if not isinstance(r, dict):
            raise InputContractError("Control receipt must be a dictionary.")
        if r.get("schema_version") != SCHEMA_VERSION:
            raise InputContractError(f"Control receipt schema_version mismatch: expected '{SCHEMA_VERSION}', got '{r.get('schema_version')}'")
        if r.get("receipt_type") != "control_case_execution_receipt":
            raise InputContractError(f"Invalid receipt_type for control receipt: '{r.get('receipt_type')}'")
        m_id = r.get("model_id")
        if not m_id:
            raise InputContractError("Control receipt missing mandatory 'model_id' field.")
        if m_id not in registered_models:
            raise InputContractError(f"Unregistered model_id '{m_id}' in control receipt. Allowed models: {sorted(list(registered_models))}")
        if m_id in seen_ctrl_models:
            raise InputContractError(f"Duplicate control receipt detected for model '{m_id}'.")
        seen_ctrl_models.add(m_id)

    # 2. Calibration receipts validation
    seen_calib = set()
    for r in (calibration_receipts or []):
        if not isinstance(r, dict):
            raise InputContractError("Calibration receipt must be a dictionary.")
        if r.get("schema_version") != SCHEMA_VERSION:
            raise InputContractError(f"Calibration receipt schema_version mismatch: expected '{SCHEMA_VERSION}', got '{r.get('schema_version')}'")
        if r.get("receipt_type") != "calibration_family_execution_receipt":
            raise InputContractError(f"Invalid receipt_type for calibration receipt: '{r.get('receipt_type')}'")
        m_id = r.get("model_id")
        if not m_id:
            raise InputContractError("Calibration receipt missing mandatory 'model_id' field.")
        if m_id not in registered_models:
            raise InputContractError(f"Unregistered model_id '{m_id}' in calibration receipt. Allowed models: {sorted(list(registered_models))}")
        fam = r.get("family_name")
        if not fam:
            raise InputContractError("Calibration receipt missing mandatory 'family_name' field.")
        if fam not in REQUIRED_CALIBRATION_FAMILIES:
            raise InputContractError(f"Unrecognized calibration family '{fam}'. Allowed families: {sorted(list(REQUIRED_CALIBRATION_FAMILIES))}")
        pair = (m_id, fam)
        if pair in seen_calib:
            raise InputContractError(f"Duplicate calibration receipt detected for model '{m_id}', family '{fam}'.")
        seen_calib.add(pair)

    # 3. Blind receipts and Selection Custody validation
    has_any_selection = (selection_record is not None or pool_commitment is not None or pool_tsv is not None or pool_anchor is not None or beacon_verification is not None or pool_manifest is not None or pool_anchor_evidence is not None)
    validated_selected = None
    selected_case_ids = None

    if has_any_selection:
        if selection_record is None or pool_commitment is None or pool_tsv is None:
            raise InputContractError(
                "Incomplete selection custody: 'selection_record', 'pool_commitment', and 'pool_tsv' must all be provided together."
            )
        validated_selected = validate_selection(
            pool_tsv,
            pool_commitment,
            selection_record,
            pool_anchor=pool_anchor,
            beacon_verification=beacon_verification,
            pool_manifest=pool_manifest,
            pool_anchor_evidence=pool_anchor_evidence
        )
        selected_case_ids = {item["case_id"] for item in validated_selected}

    seen_blind = set()
    for r in (blind_receipts or []):
        if not isinstance(r, dict):
            raise InputContractError("Blind receipt must be a dictionary.")
        if r.get("schema_version") != SCHEMA_VERSION:
            raise InputContractError(f"Blind receipt schema_version mismatch: expected '{SCHEMA_VERSION}', got '{r.get('schema_version')}'")
        if r.get("receipt_type") != "blind_case_execution_receipt":
            raise InputContractError(f"Invalid receipt_type for blind receipt: '{r.get('receipt_type')}'")
        m_id = r.get("model_id")
        if not m_id:
            raise InputContractError("Blind receipt missing mandatory 'model_id' field.")
        if m_id not in registered_models:
            raise InputContractError(f"Unregistered model_id '{m_id}' in blind receipt. Allowed models: {sorted(list(registered_models))}")
        c_id = r.get("case_id")
        if not c_id:
            raise InputContractError("Blind receipt missing mandatory 'case_id' field.")
        if selected_case_ids is not None and c_id not in selected_case_ids:
            raise InputContractError(f"Blind receipt contains case_id '{c_id}' which was NOT selected in selection custody. Allowed: {sorted(list(selected_case_ids))}")
        pair = (m_id, c_id)
        if pair in seen_blind:
            raise InputContractError(f"Duplicate blind receipt detected for model '{m_id}', case '{c_id}'.")
        seen_blind.add(pair)

    return validated_selected

def classify_completion(direct_status: str, lifted_status: str) -> str:
    """
    Computes O_completion ∈ {BOTH, L-ONLY, D-ONLY, NEITHER, NOT_EVALUABLE_INFRA}.
    """
    if direct_status == "INFRA_FAILURE" or lifted_status == "INFRA_FAILURE":
        return "NOT_EVALUABLE_INFRA"
    
    d_complete = (direct_status == "COMPLETE")
    l_complete = (lifted_status == "COMPLETE")
    
    if d_complete and l_complete:
        return "BOTH"
    elif d_complete and not l_complete:
        return "D-ONLY"
    elif not d_complete and l_complete:
        return "L-ONLY"
    else:
        return "NEITHER"

def analyze_blind_case(receipt: dict) -> dict:
    """
    Adjudicates a single blind transfer case receipt.
    """
    case_id = receipt.get("case_id", "unknown")
    model_id = receipt.get("model_id")
    if not model_id:
        raise ValueError(f"Blind receipt '{case_id}' missing mandatory 'model_id' field.")

    direct_info = receipt.get("direct", {})
    lifted_info = receipt.get("lifted", {})
    rep_search_info = receipt.get("representation_search", {})
    
    d_status = direct_info.get("final_status", "UNKNOWN")
    l_status = lifted_info.get("final_status", "UNKNOWN")
    s_status = rep_search_info.get("final_status", "UNKNOWN")
    
    o_completion = classify_completion(d_status, l_status)
    
    # Representation search outcome
    if s_status == "COMPLETE":
        rep_search_outcome = "LIFT_FOUND"
    elif s_status == "INFRA_FAILURE":
        rep_search_outcome = "INFRA_FAILURE"
    else:
        rep_search_outcome = "LIFT_NOT_FOUND"
        
    w_d = direct_info.get("verified_footprint_tokens")
    w_l = lifted_info.get("verified_footprint_tokens")
    
    # Footprint comparison ΔW is defined STRICTLY for BOTH
    if o_completion == "BOTH" and w_d is not None and w_l is not None:
        delta_w = w_l - w_d
    else:
        delta_w = None
        
    return {
        "receipt_type": "blind_case_analysis",
        "case_id": case_id,
        "model_id": model_id,
        "representation_search_outcome": rep_search_outcome,
        "o_completion": o_completion,
        "w_d": w_d,
        "w_l": w_l,
        "delta_w": delta_w,
        "delta_w_evaluated": (delta_w is not None)
    }

def analyze_calibration_family(receipt: dict) -> dict:
    """
    Adjudicates a calibration family receipt evaluating H1.
    Conditions:
    1. Marginal dividend: 2 * Δ_L^(2) <= Δ_D^(2)
    2. Cumulative amortization: W_L(T1 + T2) < W_D(T1 + T2)
    """
    family_name = receipt.get("family_name", "unknown")
    model_id = receipt.get("model_id")
    if not model_id:
        raise ValueError(f"Calibration receipt '{family_name}' missing mandatory 'model_id' field.")

    direct_info = receipt.get("direct", {})
    lifted_info = receipt.get("lifted", {})
    
    d1_status = direct_info.get("d1_status", "UNKNOWN")
    d2_status = direct_info.get("d2_status", "UNKNOWN")
    s1_status = lifted_info.get("s1_status", "UNKNOWN")
    l1_status = lifted_info.get("l1_status", "UNKNOWN")
    s2_status = lifted_info.get("s2_status", "UNKNOWN")
    l2_status = lifted_info.get("l2_status", "UNKNOWN")
    
    all_statuses = [d1_status, d2_status, s1_status, l1_status, s2_status, l2_status]
    
    if any(s == "INFRA_FAILURE" for s in all_statuses):
        return {
            "receipt_type": "calibration_family_analysis",
            "family_name": family_name,
            "model_id": model_id,
            "verdict": "NOT_EVALUABLE_INFRA",
            "marginal_dividend_satisfied": False,
            "cumulative_amortization_satisfied": False,
            "delta_l_2": None,
            "delta_d_2": None,
            "w_l_t1_t2": None,
            "w_d_t1_t2": None,
            "reason": "Transport or infrastructure failure encountered during execution."
        }
        
    if any(s != "COMPLETE" for s in all_statuses):
        return {
            "receipt_type": "calibration_family_analysis",
            "family_name": family_name,
            "model_id": model_id,
            "verdict": "NOT_EVALUABLE",
            "marginal_dividend_satisfied": False,
            "cumulative_amortization_satisfied": False,
            "delta_l_2": None,
            "delta_d_2": None,
            "w_l_t1_t2": None,
            "w_d_t1_t2": None,
            "reason": f"Incomplete verification across required proofs: statuses={all_statuses}"
        }
        
    delta_d = direct_info.get("delta_d_2")
    delta_l = lifted_info.get("delta_l_2")
    w_d_cum = direct_info.get("w_d_t1_t2")
    w_l_cum = lifted_info.get("w_l_t1_t2")
    
    if delta_d is None or delta_l is None or w_d_cum is None or w_l_cum is None:
        return {
            "receipt_type": "calibration_family_analysis",
            "family_name": family_name,
            "model_id": model_id,
            "verdict": "NOT_EVALUABLE",
            "marginal_dividend_satisfied": False,
            "cumulative_amortization_satisfied": False,
            "delta_l_2": delta_l,
            "delta_d_2": delta_d,
            "w_l_t1_t2": w_l_cum,
            "w_d_t1_t2": w_d_cum,
            "reason": "Missing token counts despite COMPLETE status."
        }
        
    # Primary integer-comparison conditions:
    marginal_ok = bool(2 * delta_l <= delta_d)
    cumulative_ok = bool(w_l_cum < w_d_cum)
    h1_pass = marginal_ok and cumulative_ok
    verdict = "PASS" if h1_pass else "REJECT"
    
    ratio = round(delta_l / delta_d, 4) if delta_d > 0 else None
    
    return {
        "receipt_type": "calibration_family_analysis",
        "family_name": family_name,
        "model_id": model_id,
        "verdict": verdict,
        "marginal_dividend_satisfied": marginal_ok,
        "cumulative_amortization_satisfied": cumulative_ok,
        "delta_l_2": delta_l,
        "delta_d_2": delta_d,
        "w_l_t1_t2": w_l_cum,
        "w_d_t1_t2": w_d_cum,
        "ratio_delta_l_over_delta_d": ratio,
        "reason": f"Marginal check: 2*{delta_l} <= {delta_d} -> {marginal_ok}; Cumulative check: {w_l_cum} < {w_d_cum} -> {cumulative_ok}"
    }

def aggregate_h1(family_analyses: list[dict]) -> str:
    """
    Conservative aggregation rule for H1 across 3 families:
    - Requires all 3 predeclared families: {fibonacci, pell, roots_of_unity}.
    - If any family is missing -> NOT_EVALUABLE.
    - PASS ⇔ all 3 families have verdict == "PASS"
    - REJECT ⇔ any family has verdict == "REJECT"
    - NOT_EVALUABLE ⇔ no REJECT, but at least one NOT_EVALUABLE
    - NOT_EVALUABLE_INFRA ⇔ no REJECT, no NOT_EVALUABLE, but at least one NOT_EVALUABLE_INFRA
    """
    if not family_analyses:
        return "NOT_EVALUABLE"
        
    present_fams = set(fa.get("family_name") for fa in family_analyses)
    if present_fams != REQUIRED_CALIBRATION_FAMILIES:
        return "NOT_EVALUABLE"
        
    verdicts = [fa.get("verdict", "UNKNOWN") for fa in family_analyses]
    
    if any(v == "REJECT" for v in verdicts):
        return "REJECT"
    if all(v == "PASS" for v in verdicts) and len(verdicts) == 3:
        return "PASS"
    if any(v == "NOT_EVALUABLE" for v in verdicts):
        return "NOT_EVALUABLE"
    if any(v == "NOT_EVALUABLE_INFRA" for v in verdicts):
        return "NOT_EVALUABLE_INFRA"
    
    return "NOT_EVALUABLE"

def analyze_control_case(receipt: dict) -> dict:
    """
    Adjudicates the Negative Control Arm receipt according to Section 2.3 pre-frozen matrix:
    - D-ONLY ⇔ CONTROL_PASS
    - BOTH & (W_D < W_L) ⇔ CONTROL_PASS
    - L-ONLY ⇔ COMPROMISED
    - BOTH & (W_L <= W_D) ⇔ COMPROMISED
    - NEITHER ⇔ CONTROL_INCONCLUSIVE
    - Transport/infrastructure failure ⇔ CONTROL_NOT_EVALUABLE_INFRA
    """
    model_id = receipt.get("model_id")
    if not model_id:
        raise ValueError("Control receipt missing mandatory 'model_id' field.")

    direct_info = receipt.get("direct", {})
    lifted_info = receipt.get("lifted", {})
    
    d_status = direct_info.get("final_status", "UNKNOWN")
    l_status = lifted_info.get("final_status", "UNKNOWN")
    
    o_completion = classify_completion(d_status, l_status)
    w_d = direct_info.get("verified_footprint_tokens")
    w_l = lifted_info.get("verified_footprint_tokens")
    
    if o_completion == "NOT_EVALUABLE_INFRA":
        verdict = "CONTROL_NOT_EVALUABLE_INFRA"
        validity = "INFRASTRUCTURE_FAILURE"
        action = "Negative control aborted due to transport/infrastructure failure."
    elif o_completion == "D-ONLY":
        verdict = "CONTROL_PASS"
        validity = "VALID"
        action = "Integrity confirmed; direct wins on flat problem."
    elif o_completion == "L-ONLY":
        verdict = "COMPROMISED"
        validity = "INVALID_STRUCTURAL_BIAS"
        action = "Protocol failure; direct branch starved or broken. Methodological conclusions of H1 and H2 are completely invalidated."
    elif o_completion == "NEITHER":
        verdict = "CONTROL_INCONCLUSIVE"
        validity = "INCONCLUSIVE"
        action = "Both branches failed; raw data preserved, no positive method-level claim may be asserted."
    elif o_completion == "BOTH":
        if w_d is not None and w_l is not None and w_d < w_l:
            verdict = "CONTROL_PASS"
            validity = "VALID"
            action = "Integrity confirmed; metric correctly penalizes unnecessary representation lifting."
        else:
            verdict = "COMPROMISED"
            validity = "INVALID_STRUCTURAL_BIAS"
            action = f"Protocol failure; metric possesses structural bias toward lifting (W_L={w_l} <= W_D={w_d}). Methodological conclusions of H1 and H2 are completely invalidated."
    else:
        verdict = "CONTROL_INCONCLUSIVE"
        validity = "INCONCLUSIVE"
        action = "Unrecognized completion state."

    return {
        "receipt_type": "control_case_analysis",
        "model_id": model_id,
        "o_completion": o_completion,
        "w_d": w_d,
        "w_l": w_l,
        "verdict": verdict,
        "protocol_validity": validity,
        "veto_active": (verdict == "COMPROMISED"),
        "operational_action": action
    }

def adjudicate_receipt(receipt_data: dict) -> dict:
    """
    Dispatches receipt to appropriate adjudicator based on receipt_type.
    """
    receipt_type = receipt_data.get("receipt_type")
    if receipt_type == "blind_case_execution_receipt":
        return analyze_blind_case(receipt_data)
    elif receipt_type == "calibration_family_execution_receipt":
        return analyze_calibration_family(receipt_data)
    elif receipt_type == "control_case_execution_receipt":
        return analyze_control_case(receipt_data)
    else:
        raise ValueError(f"Unknown or unsupported receipt_type: '{receipt_type}'")

def adjudicate_study(
    control_receipts: list[dict] | dict | None = None,
    calibration_receipts: list[dict] | None = None,
    blind_receipts: list[dict] | None = None,
    selection_record: dict | None = None,
    pool_commitment: dict | None = None,
    pool_tsv: str | bytes | None = None,
    pool_anchor: dict | None = None,
    beacon_verification: dict | None = None,
    selection_record_path: str | None = None,
    pool_commitment_path: str | None = None,
    pool_tsv_path: str | None = None,
    pool_anchor_path: str | None = None,
    beacon_verification_path: str | None = None,
    config_path: str | None = None,
    config: dict | None = None,
    control_receipt: dict | None = None,
    pool_manifest: bytes | None = None,
    pool_anchor_evidence: bytes | None = None,
    pool_manifest_path: str | None = None,
    pool_anchor_evidence_path: str | None = None
) -> dict:
    """
    Comprehensive multi-arm study adjudication under v0.17 governance.
    Evaluates:
    1. Input Contract Validation via validate_study_inputs (schema, models, no duplicates, selection custody)
    2. Negative Control Arm per model (fails closed as CONTROL_MISSING with veto if absent for that model)
    3. Primary Model H1 verdict (requires all 3 families)
    4. Replication Model H1 verdict (independent; requires all 3 families)
    5. Blind Transfer H2 case-series (verified against selection custody chain and external anchors)
    6. Definitive study_verdict derived strictly from the Primary Model.
    """
    if control_receipt is not None and control_receipts is None:
        control_receipts = [control_receipt]
    elif isinstance(control_receipts, dict):
        control_receipts = [control_receipts]

    control_receipts = control_receipts or []
    calibration_receipts = calibration_receipts or []
    blind_receipts = blind_receipts or []

    if selection_record_path and selection_record is None:
        with open(selection_record_path, "r", encoding="utf-8") as f:
            selection_record = json.load(f)
    if pool_commitment_path and pool_commitment is None:
        with open(pool_commitment_path, "r", encoding="utf-8") as f:
            pool_commitment = json.load(f)
    if pool_tsv_path and pool_tsv is None:
        with open(pool_tsv_path, "rb") as f:
            pool_tsv = f.read()
    if pool_anchor_path and pool_anchor is None:
        with open(pool_anchor_path, "r", encoding="utf-8") as f:
            pool_anchor = json.load(f)
    if beacon_verification_path and beacon_verification is None:
        with open(beacon_verification_path, "r", encoding="utf-8") as f:
            beacon_verification = json.load(f)
    if pool_manifest_path and pool_manifest is None:
        with open(pool_manifest_path, "rb") as f:
            pool_manifest = f.read()
    if pool_anchor_evidence_path and pool_anchor_evidence is None:
        with open(pool_anchor_evidence_path, "rb") as f:
            pool_anchor_evidence = f.read()

    cfg = config or load_executor_config(config_path)
    primary_id = cfg["primary_model_id"]
    replication_id = cfg["replication_model_id"]
    registered_models = [primary_id, replication_id]

    # Validate inputs before any analytical step
    validated_selected = validate_study_inputs(
        cfg,
        control_receipts=control_receipts,
        calibration_receipts=calibration_receipts,
        blind_receipts=blind_receipts,
        selection_record=selection_record,
        pool_commitment=pool_commitment,
        pool_tsv=pool_tsv,
        pool_anchor=pool_anchor,
        beacon_verification=beacon_verification,
        pool_manifest=pool_manifest,
        pool_anchor_evidence=pool_anchor_evidence
    )

    # 1. Negative Control Evaluation per model
    control_res_by_model: dict[str, dict] = {}
    veto_by_model: dict[str, bool] = {}
    veto_reason_by_model: dict[str, str | None] = {}

    for m_id in registered_models:
        ctrl_r = next((r for r in control_receipts if r.get("model_id") == m_id), None)
        if ctrl_r is None:
            ctrl_analysis = {
                "receipt_type": "control_case_analysis",
                "model_id": m_id,
                "o_completion": None,
                "w_d": None,
                "w_l": None,
                "verdict": "CONTROL_MISSING",
                "protocol_validity": "INVALID_CONTROL_MISSING",
                "veto_active": True,
                "operational_action": f"Negative control receipt was NOT provided for model '{m_id}'. No methodological conclusions may be drawn for H1 or H2."
            }
            control_res_by_model[m_id] = ctrl_analysis
            veto_by_model[m_id] = True
            veto_reason_by_model[m_id] = "CONTROL_MISSING"
        else:
            ctrl_analysis = analyze_control_case(ctrl_r)
            control_res_by_model[m_id] = ctrl_analysis
            veto_by_model[m_id] = ctrl_analysis.get("veto_active", False)
            veto_reason_by_model[m_id] = "CONTROL_COMPROMISED" if veto_by_model[m_id] else None

    # 2. Calibration H1 Evaluation per model
    calib_by_model: dict[str, list[dict]] = {m_id: [] for m_id in registered_models}
    for r in calibration_receipts:
        m_id = r["model_id"]
        calib_by_model[m_id].append(analyze_calibration_family(r))

    h1_verdicts_by_model: dict[str, dict] = {}
    for m_id in registered_models:
        role = "primary" if m_id == primary_id else "replication"
        fams = calib_by_model[m_id]
        m_veto = veto_by_model[m_id]
        m_veto_reason = veto_reason_by_model[m_id]

        if m_veto:
            verdict = "INVALIDATED_CONTROL_MISSING" if m_veto_reason == "CONTROL_MISSING" else "INVALIDATED_BY_CONTROL_VETO"
            h1_verdicts_by_model[m_id] = {
                "role": role,
                "verdict": verdict,
                "reason": f"Veto triggered by negative control for model '{m_id}' ({m_veto_reason})."
            }
        elif not fams:
            h1_verdicts_by_model[m_id] = {
                "role": role,
                "verdict": "NOT_EVALUABLE",
                "reason": f"NO_RECEIPTS_PROVIDED: No calibration receipts provided for model '{m_id}'."
            }
        else:
            present_fams = set(f.get("family_name") for f in fams)
            if present_fams != REQUIRED_CALIBRATION_FAMILIES:
                h1_verdicts_by_model[m_id] = {
                    "role": role,
                    "verdict": "NOT_EVALUABLE",
                    "reason": f"MISSING_CALIBRATION_FAMILIES: Expected {sorted(list(REQUIRED_CALIBRATION_FAMILIES))}, got {sorted(list(present_fams))}."
                }
            else:
                verdict = aggregate_h1(fams)
                h1_verdicts_by_model[m_id] = {
                    "role": role,
                    "verdict": verdict,
                    "reason": "Aggregated across complete 3-family calibration arm."
                }

    # 3. Blind H2 Evaluation per model
    blind_by_model: dict[str, list[dict]] = {m_id: [] for m_id in registered_models}
    for r in blind_receipts:
        m_id = r["model_id"]
        blind_by_model[m_id].append(analyze_blind_case(r))

    h2_summary_by_model: dict[str, dict] = {}
    for m_id in registered_models:
        role = "primary" if m_id == primary_id else "replication"
        cases = blind_by_model[m_id]
        m_veto = veto_by_model[m_id]
        m_veto_reason = veto_reason_by_model[m_id]

        comp_counts: dict[str, int] = {}
        lift_found_count = 0
        both_deltas: list[int] = []
        for c in cases:
            comp = c["o_completion"]
            comp_counts[comp] = comp_counts.get(comp, 0) + 1
            if c["representation_search_outcome"] == "LIFT_FOUND":
                lift_found_count += 1
            if c["delta_w"] is not None:
                both_deltas.append(c["delta_w"])

        if m_veto:
            status = "INVALIDATED_CONTROL_MISSING" if m_veto_reason == "CONTROL_MISSING" else "INVALIDATED_BY_CONTROL_VETO"
            reason = f"Veto triggered by negative control for model '{m_id}' ({m_veto_reason})."
        elif not cases:
            status = "NOT_EVALUABLE"
            reason = f"NO_RECEIPTS_PROVIDED: No blind receipts provided for model '{m_id}'."
        else:
            if validated_selected is None:
                status = "NOT_EVALUABLE"
                reason = "MISSING_SELECTION_CUSTODY: No verified selection custody provided to authenticate blind case cohort."
            elif pool_anchor is None:
                status = "NOT_EVALUABLE_POOL_TIMESTAMP"
                reason = "MISSING_POOL_ANCHOR_RECEIPT: External proof of pool publication timestamp prior to beacon round was not provided."
            elif beacon_verification is None:
                status = "NOT_EVALUABLE_BEACON_AUTHENTICITY"
                reason = "MISSING_BEACON_AUTHENTICITY_RECEIPT: External BLS verification receipt for drand quicknet beacon was not provided."
            else:
                expected_ids = {item["case_id"] for item in validated_selected}
                observed_ids = set(c["case_id"] for c in cases)
                if observed_ids != expected_ids:
                    status = "NOT_EVALUABLE"
                    reason = f"MISSING_BLIND_CASES: Expected {sorted(list(expected_ids))}, got {sorted(list(observed_ids))}."
                else:
                    status = "VALID_DESCRIPTIVE_SERIES"
                    reason = "Complete evaluation across all 3 verified selected blind cases."

        h2_summary_by_model[m_id] = {
            "role": role,
            "total_cases": len(cases),
            "lift_found_count": lift_found_count,
            "completion_distribution": comp_counts,
            "both_deltas": both_deltas,
            "status": status,
            "reason": reason
        }

    # Top-level study verdict derived strictly from Primary Model
    primary_h1 = h1_verdicts_by_model.get(primary_id, {})
    primary_ctrl = control_res_by_model.get(primary_id, {})
    repl_h1 = h1_verdicts_by_model.get(replication_id, {})
    repl_ctrl = control_res_by_model.get(replication_id, {})

    if primary_ctrl.get("verdict") == "CONTROL_MISSING":
        study_verdict = "INVALIDATED_CONTROL_MISSING"
    elif primary_ctrl.get("veto_active"):
        study_verdict = "INVALIDATED_BY_CONTROL_VETO"
    else:
        study_verdict = primary_h1.get("verdict", "NOT_EVALUABLE")

    if repl_ctrl.get("verdict") == "CONTROL_MISSING":
        repl_verdict = "INVALIDATED_CONTROL_MISSING"
    elif repl_ctrl.get("veto_active"):
        repl_verdict = "INVALIDATED_BY_CONTROL_VETO"
    else:
        repl_verdict = repl_h1.get("verdict", "NOT_EVALUABLE")

    return {
        "schema_version": SCHEMA_VERSION,
        "study_verdict": study_verdict,
        "basis": "PRIMARY_MODEL_ONLY",
        "replication": {
            "status": repl_verdict,
            "verdict": repl_verdict,
            "interpretation": "SECONDARY_REPLICATION_ONLY"
        },
        "study_adjudication": {
            "model_configuration": {
                "primary_model_id": primary_id,
                "replication_model_id": replication_id
            },
            "study_verdict": study_verdict,
            "basis": "PRIMARY_MODEL_ONLY",
            "replication": {
                "status": repl_verdict,
                "verdict": repl_verdict,
                "interpretation": "SECONDARY_REPLICATION_ONLY"
            },
            "negative_control_by_model": control_res_by_model,
            "negative_control": control_res_by_model.get(primary_id),
            "veto_active": veto_by_model.get(primary_id, False),
            "veto_reason": veto_reason_by_model.get(primary_id),
            "h1_amortization": {
                "verdicts_by_model": h1_verdicts_by_model,
                "families_by_model": calib_by_model
            },
            "h2_blind_transfer": {
                "summaries_by_model": h2_summary_by_model,
                "cases_by_model": blind_by_model
            }
        }
    }

def main():
    parser = argparse.ArgumentParser(description="representation-lifting-s1 Analysis & Adjudication Tool")
    parser.add_argument("--receipt", type=str, help="Path to a single receipt JSON file to adjudicate")
    parser.add_argument("--control-receipt", type=str, help="Path to negative control receipt JSON file (can be repeated or use --control-receipts)")
    parser.add_argument("--control-receipts", nargs="*", default=[], help="Paths to negative control receipt JSON files")
    parser.add_argument("--calibration-receipts", nargs="*", default=[], help="Paths to calibration family receipt JSON files")
    parser.add_argument("--blind-receipts", nargs="*", default=[], help="Paths to blind case receipt JSON files")
    parser.add_argument("--selection-record", type=str, help="Optional path to selection record JSON file (drand selection artifact)")
    parser.add_argument("--pool-commitment", type=str, help="Optional path to pool_commitment.json file")
    parser.add_argument("--pool-tsv", type=str, help="Optional path to POOL.tsv file")
    parser.add_argument("--pool-anchor", type=str, help="Optional path to pool_anchor_receipt.json file")
    parser.add_argument("--beacon-verification", type=str, help="Optional path to beacon_verification_receipt.json file")
    parser.add_argument("--pool-manifest", type=str, help="Path to pool_bundle_manifest.json (required with --pool-anchor, v0.21)")
    parser.add_argument("--pool-anchor-evidence", type=str, help="Path to archived raw Rekor evidence JSON (required with --pool-anchor, v0.21)")
    parser.add_argument("--all-from-dir", type=str, help="Directory containing receipt files to automatically collect and adjudicate")
    parser.add_argument("--config", type=str, help="Optional path to executor_config.json")
    parser.add_argument("--out", type=str, help="Optional output JSON path for the adjudication report")
    
    args = parser.parse_args()
    
    if args.receipt:
        with open(args.receipt, "r", encoding="utf-8") as f:
            data = json.load(f)
        result = adjudicate_receipt(data)
        out_json = json.dumps(result, indent=2)
        print(out_json)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(out_json)
        sys.exit(0)
        
    control_data = []
    calib_data = []
    blind_data = []
    sel_data = None
    pool_comm_data = None
    pool_bytes_data = None
    pool_anchor_data = None
    beacon_verif_data = None
    
    if args.selection_record:
        with open(args.selection_record, "r", encoding="utf-8") as f:
            sel_data = json.load(f)
    if args.pool_commitment:
        with open(args.pool_commitment, "r", encoding="utf-8") as f:
            pool_comm_data = json.load(f)
    if args.pool_tsv:
        with open(args.pool_tsv, "rb") as f:
            pool_bytes_data = f.read()
    if args.pool_anchor:
        with open(args.pool_anchor, "r", encoding="utf-8") as f:
            pool_anchor_data = json.load(f)
    if args.beacon_verification:
        with open(args.beacon_verification, "r", encoding="utf-8") as f:
            beacon_verif_data = json.load(f)
    
    if args.all_from_dir:
        if not os.path.isdir(args.all_from_dir):
            print(f"Error: Directory '{args.all_from_dir}' not found.", file=sys.stderr)
            sys.exit(1)
        for fname in os.listdir(args.all_from_dir):
            if fname.endswith(".json") and "receipt" in fname:
                fp = os.path.join(args.all_from_dir, fname)
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        d = json.load(f)
                    rtype = d.get("receipt_type")
                    if rtype == "control_case_execution_receipt":
                        control_data.append(d)
                    elif rtype == "calibration_family_execution_receipt":
                        calib_data.append(d)
                    elif rtype == "blind_case_execution_receipt":
                        blind_data.append(d)
                except Exception:
                    pass
    else:
        if args.control_receipt:
            with open(args.control_receipt, "r", encoding="utf-8") as f:
                control_data.append(json.load(f))
        for cp in args.control_receipts:
            with open(cp, "r", encoding="utf-8") as f:
                control_data.append(json.load(f))
        for cp in args.calibration_receipts:
            with open(cp, "r", encoding="utf-8") as f:
                calib_data.append(json.load(f))
        for bp in args.blind_receipts:
            with open(bp, "r", encoding="utf-8") as f:
                blind_data.append(json.load(f))
                
    if not control_data and not calib_data and not blind_data:
        parser.print_help(sys.stderr)
        sys.exit(1)
        
    study_report = adjudicate_study(
        control_receipts=control_data,
        calibration_receipts=calib_data,
        blind_receipts=blind_data,
        selection_record=sel_data,
        pool_commitment=pool_comm_data,
        pool_tsv=pool_bytes_data,
        pool_anchor=pool_anchor_data,
        beacon_verification=beacon_verif_data,
        pool_manifest_path=args.pool_manifest,
        pool_anchor_evidence_path=args.pool_anchor_evidence,
        config_path=args.config
    )
    
    out_json = json.dumps(study_report, indent=2)
    print(out_json)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out_json)
            
    sys.exit(0)

if __name__ == "__main__":
    main()
