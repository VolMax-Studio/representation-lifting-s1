#!/usr/bin/env python3
"""Provider-neutral launcher and contract Gate 5.

Gate 5 verifies the selected adapter contract and custody implementation.  It
does not call a provider and provider availability cannot block the project.
Model identity is declared per execution and confirmed on every delivered turn.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.execution_adapter import (
    ModelRequest, build_adapter, canonical_json_bytes, sha256_bytes, sha256_file,
    validate_adapter_config, verify_turn_custody,
)

DEFAULT_ADAPTER = ROOT / "execution" / "provider-neutral-default.json"
DEFAULT_RUN_ROOT = ROOT / "execution-runs" / "provider-neutral"
SCIENTIFIC_BINDINGS = (
    "tools/executor_harness.py",
    "tools/analyze.py",
    "tools/check_bridge.py",
    "tools/prepare_blind_targets.py",
    "tools/pool_custody.py",
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()


def gate5(adapter_path: Path, run_root: Path, execution_id: str, model_id: str) -> dict:
    config = load_json(adapter_path)
    validation = validate_adapter_config(config)
    if not validation["contract_pass"]:
        raise RuntimeError("ADAPTER_CONTRACT_FAIL:" + ";".join(validation["errors"]))
    gate_dir = run_root / "gate5"
    gate_dir.mkdir(parents=True, exist_ok=False)
    adapter_copy = gate_dir / "adapter_contract.json"
    adapter_copy.write_bytes(canonical_json_bytes(config))
    adapter_sha = sha256_file(adapter_copy)
    (gate_dir / "adapter_contract.json.sha256").write_text(adapter_sha + "\n", encoding="utf-8")
    bindings = {
        relative: sha256_file(ROOT / relative)
        for relative in SCIENTIFIC_BINDINGS
    }
    receipt = {
        "schema_version": "representation-lifting-gate5-adapter-contract/v1",
        "execution_id": execution_id,
        "declared_model_id": model_id,
        "adapter_id": config["adapter_id"],
        "adapter_kind": config["kind"],
        "adapter_contract_sha256": adapter_sha,
        "scientific_bindings": bindings,
        "provider_contacted": False,
        "provider_availability_checked": False,
        "direct_api_required": False,
        "credentials_in_repository": False,
        "custody_contract": {
            "request_bytes_hashed": True,
            "response_bytes_hashed_if_delivered": True,
            "delivery_status_required": True,
            "timestamps_required": True,
            "declared_and_observed_model_identity_required": True,
        },
        "gate5_pass": True,
        "outcome_visibility": "NONE",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_commit": git_head(),
    }
    receipt_bytes = canonical_json_bytes(receipt)
    (gate_dir / "gate5_receipt.json").write_bytes(receipt_bytes)
    (gate_dir / "gate5_receipt.json.sha256").write_text(sha256_bytes(receipt_bytes) + "\n", encoding="utf-8")
    return receipt


def require_gate5(run_root: Path, adapter_path: Path, execution_id: str, model_id: str) -> dict:
    path = run_root / "gate5" / "gate5_receipt.json"
    if not path.is_file():
        raise RuntimeError("GATE5_ADAPTER_CONTRACT_RECEIPT_MISSING")
    receipt = load_json(path)
    if receipt.get("gate5_pass") is not True:
        raise RuntimeError("GATE5_ADAPTER_CONTRACT_NOT_PASS")
    if receipt.get("execution_id") != execution_id or receipt.get("declared_model_id") != model_id:
        raise RuntimeError("GATE5_EXECUTION_IDENTITY_MISMATCH")
    config = load_json(adapter_path)
    if receipt.get("adapter_contract_sha256") != sha256_bytes(canonical_json_bytes(config)):
        raise RuntimeError("GATE5_ADAPTER_CONTRACT_CHANGED")
    for relative, expected in receipt.get("scientific_bindings", {}).items():
        if sha256_file(ROOT / relative) != expected:
            raise RuntimeError(f"GATE5_SCIENTIFIC_BINDING_CHANGED:{relative}")
    return receipt


def adapter_call(adapter, execution_id: str, block_root: Path, activate):
    counters: dict[tuple[str, str], int] = {}

    def call(model_id, messages, system_prompt, remaining_wallclock, config, transcript):
        case_id = activate._CURRENT_CASE_ID or "unspecified_case"
        branch = activate._CURRENT_BRANCH_LABEL or activate._CURRENT_ROLE or "unspecified_branch"
        key = (case_id, branch)
        turn = counters.get(key, 0)
        counters[key] = turn + 1
        request = ModelRequest(
            execution_id=execution_id,
            turn_number=turn,
            declared_model_id=model_id,
            system_prompt=system_prompt,
            messages=messages,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
        )
        branch_root = block_root / "branch_artifacts" / case_id / branch
        turn_dir = branch_root / f"turn_{turn:04d}"
        result = adapter.execute(request, turn_dir, min(remaining_wallclock, 10800.0))
        custody = verify_turn_custody(turn_dir)
        metadata_dir = branch_root / "transport_metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        compatibility_metadata = {
            "schema_version": "representation-lifting-provider-neutral-transport-metadata/v1",
            "turn_number": turn,
            "model_returned": result.observed_model_id,
            "assistant_model": result.observed_model_id,
            "declared_model_id": model_id,
            "observed_model_id": result.observed_model_id,
            "delivery_status": result.delivery_status,
            "response_delivered": result.delivery_status == "DELIVERED",
            "adapter_id": adapter.config["adapter_id"],
            "custody_pass": custody["custody_pass"],
            "started_at_utc": result.started_at_utc,
            "completed_at_utc": result.completed_at_utc,
        }
        metadata_bytes = canonical_json_bytes(compatibility_metadata)
        metadata_path = metadata_dir / f"transport_metadata_{turn}.json"
        metadata_path.write_bytes(metadata_bytes)
        Path(str(metadata_path) + ".sha256").write_text(
            sha256_bytes(metadata_bytes) + "\n", encoding="utf-8"
        )
        transcript.append({
            "event": "execution_adapter_result",
            "adapter_id": adapter.config["adapter_id"],
            "turn": turn,
            "declared_model_id": model_id,
            "observed_model_id": result.observed_model_id,
            "delivery_status": result.delivery_status,
            "custody_pass": custody["custody_pass"],
        })
        if not custody["custody_pass"]:
            return "", "CUSTODY_FAILURE", True
        if result.delivery_status != "DELIVERED":
            return "", "NOT_DELIVERED", True
        return result.response_text, result.transport_metadata.get("stop_reason", "end_turn"), False

    return call


def execute_block(adapter_path: Path, run_root: Path, execution_id: str, model_id: str) -> None:
    """Execute the frozen scientific block; responses stay sealed until audit."""
    require_gate5(run_root, adapter_path, execution_id, model_id)
    if (run_root / "block").exists():
        raise RuntimeError("EXECUTION_BLOCK_ALREADY_STARTED")
    config = load_json(adapter_path)
    adapter = build_adapter(config)
    from tools import a1_activate as activate
    from tools import executor_harness as harness

    block = run_root / "block"
    block.mkdir(parents=True, exist_ok=False)
    legacy_config = load_json(ROOT / "evidence" / "amendment_a1" / "a1_transport_config.json")
    legacy_config["execution_evidence_namespace"] = "SUPERSEDED_BY_PROVIDER_NEUTRAL_RUNTIME"
    legacy_config["surfaces"]["primary"] = {
        "pinned_model_id": model_id,
        "allowed_model_labels": [model_id],
        "surface_type": config["kind"],
        "surface_version": config["schema_version"],
        "plan_tier": "OPERATOR_SUPPLIED_IF_APPLICABLE",
        "model_identity_evidence": "PER_TURN_DECLARED_AND_OBSERVED_IDENTITY",
        "inference_controls_pinned": {},
        "system_role_handling": config.get("system_role_handling"),
        "message_history_handling": config.get("message_history_handling"),
    }
    runtime_config_path = block / "adapter_runtime_config.json"
    runtime_config_path.write_bytes(canonical_json_bytes(legacy_config))
    activate.configure(
        a1_config_path=str(runtime_config_path),
        artifact_dir=str(block / "branch_artifacts"),
        sealed_dir=str(block / "sealed_transcripts"),
        receipt_dir=str(block / "receipts"),
    )
    harness.call_model_api_with_resilience = adapter_call(adapter, execution_id, block, activate)
    jobs = [
        ("negative_control", lambda: harness.run_control_case(model_id)),
        ("calibration_fibonacci", lambda: harness.run_calibration_family("fibonacci", model_id)),
        ("calibration_pell", lambda: harness.run_calibration_family("pell", model_id)),
        ("calibration_roots_of_unity", lambda: harness.run_calibration_family("roots_of_unity", model_id)),
        ("proofnet-108", lambda: harness.run_blind_case("proofnet-108", str(ROOT / "targets/proofnet-108.lean"), model_id)),
        ("proofnet-083", lambda: harness.run_blind_case("proofnet-083", str(ROOT / "targets/proofnet-083.lean"), model_id)),
        ("proofnet-267", lambda: harness.run_blind_case("proofnet-267", str(ROOT / "targets/proofnet-267.lean"), model_id)),
    ]
    started = {
        "schema_version": "representation-lifting-provider-neutral-block/v1",
        "execution_id": execution_id, "declared_model_id": model_id,
        "adapter_id": config["adapter_id"], "order": [label for label, _ in jobs],
        "outcome_visibility": "NONE", "started_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (block / "BLOCK_STARTED.json").write_bytes(canonical_json_bytes(started))
    for _, job in jobs:
        job()
    index = {
        **started,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "pre_outcome_audit": "REQUIRED",
    }
    (block / "SEALED_BLOCK_INDEX.json").write_bytes(canonical_json_bytes(index))


def audit_custody(run_root: Path, adapter_path: Path, execution_id: str, model_id: str) -> dict:
    require_gate5(run_root, adapter_path, execution_id, model_id)
    block = run_root / "block"
    if not (block / "SEALED_BLOCK_INDEX.json").is_file():
        raise RuntimeError("SEALED_BLOCK_INDEX_MISSING")
    turns = sorted((block / "branch_artifacts").glob("*/*/turn_*"))
    if not turns:
        raise RuntimeError("NO_TRANSPORT_TURNS_FOUND")
    failures = {turn.name: verify_turn_custody(turn) for turn in turns}
    failures = {name: result for name, result in failures.items() if not result["custody_pass"]}
    if failures:
        raise RuntimeError("TURN_CUSTODY_FAIL:" + json.dumps(failures, sort_keys=True))
    seals = sorted((block / "sealed_transcripts").glob("*.tar"))
    if not seals:
        raise RuntimeError("NO_SEALED_BRANCH_TRANSCRIPTS")
    for seal in seals:
        sidecar = Path(str(seal) + ".sha256")
        if not sidecar.is_file() or sidecar.read_text(encoding="utf-8").split()[0] != sha256_file(seal):
            raise RuntimeError(f"SEALED_BRANCH_HASH_MISMATCH:{seal.name}")
    receipt = {
        "schema_version": "representation-lifting-provider-neutral-pre-outcome-audit/v1",
        "execution_id": execution_id, "declared_model_id": model_id,
        "transport_turns_verified": len(turns), "sealed_branches_verified": len(seals),
        "audit_pass": True, "outcome_content_opened": False, "outcome_visibility": "NONE",
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (block / "PRE_OUTCOME_AUDIT_PASS.json").write_bytes(canonical_json_bytes(receipt))
    return receipt


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="provider-neutral execution launcher")
    parser.add_argument("--adapter", type=Path, default=DEFAULT_ADAPTER)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--model-id", required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--gate5", action="store_true")
    action.add_argument("--execute-block", action="store_true")
    action.add_argument("--audit-custody", action="store_true")
    args = parser.parse_args(argv)
    run_root = args.run_root.resolve()
    if args.gate5:
        gate5(args.adapter.resolve(), run_root, args.execution_id, args.model_id)
        print("GATE 5 ADAPTER CONTRACT PASS — PROVIDER NOT CONTACTED — OUTCOME VISIBILITY NONE")
    elif args.execute_block:
        execute_block(args.adapter.resolve(), run_root, args.execution_id, args.model_id)
        print("BLOCK SEALED — PRE-OUTCOME AUDIT REQUIRED — OUTCOME VISIBILITY NONE")
    else:
        audit_custody(run_root, args.adapter.resolve(), args.execution_id, args.model_id)
        print("PRE-OUTCOME CUSTODY AUDIT PASS — OUTCOME MAY NOW BE OPENED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
