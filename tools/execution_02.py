#!/usr/bin/env python3
"""Signed, fail-closed launcher for the s1-execution-02 instance."""

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import time as real_time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import a1_surface_bridge as bridge


MANIFEST_PATH = ROOT / "evidence" / "execution_02" / "EXECUTION_MANIFEST.json"
MANIFEST_REL = "evidence/execution_02/EXECUTION_MANIFEST.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_sha256(path: Path) -> str:
    """Hash the sorted relative path, NUL, file hash, newline for every file."""
    digest = hashlib.sha256()
    files = sorted(p for p in path.rglob("*") if p.is_file())
    if not files:
        raise RuntimeError(f"EMPTY_BOUND_TREE:{path}")
    for item in files:
        relative = item.relative_to(path).as_posix().encode("utf-8")
        digest.update(relative + b"\0" + sha256_file(item).encode("ascii") + b"\n")
    return digest.hexdigest()


def load_manifest() -> dict:
    with MANIFEST_PATH.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def git_output(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def verify_tag_at_commit(tag: str, expected_commit: str) -> None:
    subprocess.run(
        ["git", "verify-tag", tag], cwd=ROOT, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    actual = git_output("rev-parse", f"{tag}^{{}}")
    if actual != expected_commit:
        raise RuntimeError(
            f"RATIFICATION_TAG_COMMIT_MISMATCH:{tag}:expected={expected_commit}:actual={actual}"
        )


def require_file_binding(binding: dict) -> None:
    path = ROOT / binding["path"]
    actual = sha256_file(path)
    if actual != binding["sha256"]:
        raise RuntimeError(
            f"HASH_MISMATCH:{binding['path']}:expected={binding['sha256']}:actual={actual}"
        )


def verify_candidate(manifest: dict) -> None:
    for prior in manifest["prior_ratifications"]:
        verify_tag_at_commit(prior["tag"], prior["commit"])
    for binding in manifest["critical_file_bindings"]:
        require_file_binding(binding)
    evidence = manifest["consumed_recovery_evidence"]
    actual_tree = tree_sha256(ROOT / evidence["path"])
    if actual_tree != evidence["tree_sha256"]:
        raise RuntimeError(
            f"RECOVERY_EVIDENCE_TREE_MISMATCH:expected={evidence['tree_sha256']}:actual={actual_tree}"
        )


def verify_execution_ratification(manifest: dict) -> str:
    tag = manifest["required_ratification_tag"]
    subprocess.run(
        ["git", "verify-tag", tag], cwd=ROOT, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    commit = git_output("rev-parse", f"{tag}^{{}}")
    head = git_output("rev-parse", "HEAD")
    if commit != head:
        raise RuntimeError(f"EXECUTION_02_TAG_NOT_AT_HEAD:tag={commit}:head={head}")
    return commit


def verify_signed_tree(manifest: dict, commit: str) -> None:
    paths = [MANIFEST_REL] + [b["path"] for b in manifest["critical_file_bindings"]]
    for relative in sorted(set(paths)):
        committed = subprocess.run(
            ["git", "show", f"{commit}:{relative}"], cwd=ROOT, check=True,
            capture_output=True,
        ).stdout
        path = ROOT / relative
        if not path.is_file() or path.read_bytes() != committed:
            raise RuntimeError(f"SIGNED_TREE_WORKTREE_MISMATCH:{relative}")


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def require_gate5_window(manifest: dict, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    policy = manifest["availability_policy"]
    earliest = parse_timestamp(policy["gate5_not_before"])
    latest = parse_timestamp(policy["gate5_start_deadline"])
    if now < earliest:
        raise RuntimeError(f"GATE5_TOO_EARLY:not_before={policy['gate5_not_before']}")
    if now > latest:
        raise RuntimeError(f"GATE5_START_WINDOW_EXPIRED:deadline={policy['gate5_start_deadline']}")


def runtime_executor_config(manifest: dict) -> dict:
    frozen_path = ROOT / manifest["frozen_executor_config"]["path"]
    config = json.loads(frozen_path.read_text(encoding="utf-8"))
    policy = manifest["availability_policy"]
    config = copy.deepcopy(config)
    config["transport_policy"] = {
        "max_attempts_per_turn": policy["max_attempts_per_logical_turn"],
        "retryable_http_codes": config["transport_policy"]["retryable_http_codes"],
        "backoff_seconds": policy["backoff_seconds"],
        "request_timeout_seconds": config["transport_policy"]["request_timeout_seconds"],
    }
    return config


class AvailabilityClock:
    """Virtual clock that excludes only policy-defined availability sleeps."""

    def __init__(self, sleeper=real_time.sleep):
        self._sleeper = sleeper
        self._excluded = 0.0

    def time(self) -> float:
        return real_time.time() - self._excluded

    def monotonic(self) -> float:
        return real_time.monotonic() - self._excluded

    def perf_counter(self) -> float:
        return real_time.perf_counter() - self._excluded

    def sleep(self, seconds: float) -> None:
        started = real_time.monotonic()
        self._sleeper(seconds)
        self._excluded += max(0.0, real_time.monotonic() - started)

    def __getattr__(self, name):
        return getattr(real_time, name)


def gate5_dir(manifest: dict) -> Path:
    return ROOT / manifest["evidence_namespace"] / "gate5"


def run_gate5(manifest: dict) -> dict:
    verify_candidate(manifest)
    commit = verify_execution_ratification(manifest)
    verify_signed_tree(manifest, commit)
    require_gate5_window(manifest)
    output = gate5_dir(manifest)
    if output.exists():
        raise RuntimeError("EXECUTION_02_GATE5_ALREADY_STARTED")
    output.mkdir(parents=True, exist_ok=False)
    start = {
        "schema_version": "representation-lifting-execution-02-start/v1",
        "instance": manifest["instance"],
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "ratified_commit": commit,
        "ratification_tag": manifest["required_ratification_tag"],
        "outcome_visibility": "NONE",
    }
    (output / "EXECUTION_STARTED.json").write_text(
        json.dumps(start, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    a1_config = json.loads(
        (ROOT / manifest["a1_transport_config"]["path"]).read_text(encoding="utf-8")
    )
    clock = AvailabilityClock()
    original_bridge_time = bridge.time
    bridge.time = clock
    try:
        return bridge.run_gate5_probe(
            model_id="claude-sonnet-4-6",
            a1_config=a1_config,
            artifact_dir=str(output),
            config=runtime_executor_config(manifest),
            root_dir=str(ROOT),
            skip_preflight=False,
        )
    finally:
        bridge.time = original_bridge_time


def require_gate5_pass(manifest: dict) -> None:
    receipt = gate5_dir(manifest) / "gate5_receipt.json"
    if not receipt.is_file():
        raise RuntimeError("EXECUTION_02_GATE5_PASS_RECEIPT_MISSING")
    data = json.loads(receipt.read_text(encoding="utf-8"))
    if data.get("gate5_pass") is not True or data.get("exact_match") is not True:
        raise RuntimeError("EXECUTION_02_GATE5_NOT_PASS")
    custody = bridge.validate_turn_transport_custody(str(gate5_dir(manifest)), 0)
    if custody.get("custody_pass") is not True:
        raise RuntimeError("EXECUTION_02_GATE5_CUSTODY_FAIL")


def _install_a2_runtime(manifest: dict, clock: AvailabilityClock):
    """Activate A1 custody with the A2 finite availability policy."""
    from tools import a1_activate as activate
    from tools import executor_harness as harness

    run_root = ROOT / manifest["evidence_namespace"] / "block"
    activate.configure(
        a1_config_path=str(ROOT / manifest["a1_transport_config"]["path"]),
        artifact_dir=str(run_root / "artifacts"),
        sealed_dir=str(run_root / "sealed_transcripts"),
        receipt_dir=str(run_root / "receipts"),
    )
    runtime_config = runtime_executor_config(manifest)

    def a2_inference(model_id, messages, system_prompt, remaining_wallclock, config, transcript):
        case_id = activate._CURRENT_CASE_ID or "unspecified_case"
        branch = activate._CURRENT_BRANCH_LABEL or activate._CURRENT_ROLE or "unspecified_branch"
        branch_dir = Path(activate._get_base_artifact_dir()) / case_id / branch
        branch_dir.mkdir(parents=True, exist_ok=True)
        turn_key = f"{model_id}::{branch_dir}"
        turn_number = activate._get_and_increment_turn(turn_key)
        return bridge.a1_call_surface(
            model_id=model_id,
            messages=messages,
            system_prompt=system_prompt,
            remaining_wallclock=remaining_wallclock,
            config=runtime_config,
            transcript=transcript,
            a1_config=activate._get_a1_config(),
            artifact_dir=str(branch_dir),
            turn_number=turn_number,
        )

    harness.call_model_api_with_resilience = a2_inference
    harness.time = clock
    bridge.time = clock
    return activate, harness


def _has_infra_failure(value) -> bool:
    if isinstance(value, dict):
        return any(_has_infra_failure(v) for v in value.values())
    if isinstance(value, list):
        return any(_has_infra_failure(v) for v in value)
    return value == "INFRA_FAILURE"


def execute_block(manifest: dict) -> dict:
    """Run the frozen complete block without printing or analyzing outcomes."""
    verify_candidate(manifest)
    commit = verify_execution_ratification(manifest)
    verify_signed_tree(manifest, commit)
    require_gate5_pass(manifest)
    block_root = ROOT / manifest["evidence_namespace"] / "block"
    if block_root.exists():
        raise RuntimeError("EXECUTION_02_BLOCK_ALREADY_STARTED")
    block_root.mkdir(parents=True, exist_ok=False)
    (block_root / "BLOCK_STARTED.json").write_text(json.dumps({
        "schema_version": "representation-lifting-execution-02-block-start/v1",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "ratified_commit": commit,
        "order": manifest["block_order"],
        "outcome_visibility": "NONE",
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    clock = AvailabilityClock()
    original_bridge_time = bridge.time
    activate, harness = _install_a2_runtime(manifest, clock)
    receipts = []
    try:
        jobs = [
            ("negative_control", lambda: harness.run_control_case("claude-sonnet-4-6")),
            ("calibration_fibonacci", lambda: harness.run_calibration_family("fibonacci", "claude-sonnet-4-6")),
            ("calibration_pell", lambda: harness.run_calibration_family("pell", "claude-sonnet-4-6")),
            ("calibration_roots_of_unity", lambda: harness.run_calibration_family("roots_of_unity", "claude-sonnet-4-6")),
            ("proofnet-108", lambda: harness.run_blind_case("proofnet-108", str(ROOT / "targets/proofnet-108.lean"), "claude-sonnet-4-6")),
            ("proofnet-083", lambda: harness.run_blind_case("proofnet-083", str(ROOT / "targets/proofnet-083.lean"), "claude-sonnet-4-6")),
            ("proofnet-267", lambda: harness.run_blind_case("proofnet-267", str(ROOT / "targets/proofnet-267.lean"), "claude-sonnet-4-6")),
        ]
        for label, job in jobs:
            report = job()
            receipt_dir = block_root / "receipts"
            candidates = sorted(receipt_dir.glob(f"*{label.replace('negative_control', 'control').replace('calibration_', '')}*claude-sonnet-4-6.json"))
            receipts.append({
                "label": label,
                "receipt_paths": [p.relative_to(ROOT).as_posix() for p in candidates],
                "receipt_sha256": {p.name: sha256_file(p) for p in candidates},
            })
            if _has_infra_failure(report):
                raise RuntimeError(f"EXECUTION_02_AVAILABILITY_EXHAUSTED:{label}")
    finally:
        bridge.time = original_bridge_time

    index = {
        "schema_version": "representation-lifting-execution-02-sealed-index/v1",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "order": manifest["block_order"],
        "receipts": receipts,
        "outcome_visibility": "NONE",
        "pre_outcome_audit": "REQUIRED",
    }
    (block_root / "SEALED_BLOCK_INDEX.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return index


def audit_sealed_block(manifest: dict) -> dict:
    """Custody-only audit. Does not read response text or evaluate outcomes."""
    verify_candidate(manifest)
    commit = verify_execution_ratification(manifest)
    verify_signed_tree(manifest, commit)
    require_gate5_pass(manifest)
    block_root = ROOT / manifest["evidence_namespace"] / "block"
    index_path = block_root / "SEALED_BLOCK_INDEX.json"
    if not index_path.is_file():
        raise RuntimeError("SEALED_BLOCK_INDEX_MISSING")
    expected_receipts = [
        "execution_receipt_control_claude-sonnet-4-6.json",
        "execution_receipt_calibration_fibonacci_claude-sonnet-4-6.json",
        "execution_receipt_calibration_pell_claude-sonnet-4-6.json",
        "execution_receipt_calibration_roots_of_unity_claude-sonnet-4-6.json",
        "execution_receipt_blind_proofnet-108_claude-sonnet-4-6.json",
        "execution_receipt_blind_proofnet-083_claude-sonnet-4-6.json",
        "execution_receipt_blind_proofnet-267_claude-sonnet-4-6.json",
    ]
    receipt_dir = block_root / "receipts"
    for name in expected_receipts:
        path = receipt_dir / name
        if not path.is_file():
            raise RuntimeError(f"EXPECTED_RECEIPT_MISSING:{name}")

    seals = sorted((block_root / "sealed_transcripts").glob("*.tar"))
    if len(seals) != 29:
        raise RuntimeError(f"SEALED_BRANCH_COUNT_MISMATCH:expected=29:actual={len(seals)}")
    for seal in seals:
        sidecar = Path(str(seal) + ".sha256")
        if not sidecar.is_file() or sidecar.read_text(encoding="utf-8").split()[0] != sha256_file(seal):
            raise RuntimeError(f"SEALED_BRANCH_HASH_MISMATCH:{seal.name}")

    audited_turns = 0
    artifacts = block_root / "artifacts"
    for metadata in sorted(artifacts.glob("*/*/transport_metadata/transport_metadata_*.json")):
        turn = int(metadata.stem.rsplit("_", 1)[1])
        branch_dir = metadata.parents[1]
        custody = bridge.validate_turn_transport_custody(str(branch_dir), turn)
        if custody.get("custody_pass") is not True:
            raise RuntimeError(f"TURN_CUSTODY_FAIL:{branch_dir.relative_to(ROOT)}:{turn}")
        audited_turns += 1
    if audited_turns == 0:
        raise RuntimeError("NO_TRANSPORT_TURNS_FOUND")

    audit = {
        "schema_version": "representation-lifting-execution-02-pre-outcome-audit/v1",
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "ratified_commit": commit,
        "expected_receipts_present": len(expected_receipts),
        "sealed_branches_verified": len(seals),
        "transport_turns_verified": audited_turns,
        "audit_pass": True,
        "outcome_content_opened": False,
        "outcome_visibility": "NONE",
    }
    audit_path = block_root / "PRE_OUTCOME_AUDIT_PASS.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return audit


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="s1-execution-02 signed launcher")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify-candidate", action="store_true")
    group.add_argument("--execute-gate5", action="store_true")
    group.add_argument("--execute-block", action="store_true")
    group.add_argument("--audit-sealed-block", action="store_true")
    args = parser.parse_args(argv)
    manifest = load_manifest()
    if args.verify_candidate:
        verify_candidate(manifest)
        print("EXECUTION_02 CANDIDATE VERIFIED — OUTCOME VISIBILITY NONE")
        return 0
    if args.execute_gate5:
        result = run_gate5(manifest)
        print("EXECUTION_02 GATE5 PASS" if result.get("gate5_pass") else "EXECUTION_02 GATE5 HALT")
        return 0 if result.get("gate5_pass") else 1
    if args.execute_block:
        execute_block(manifest)
        print("EXECUTION_02 BLOCK SEALED — PRE-OUTCOME AUDIT REQUIRED — OUTCOME VISIBILITY NONE")
        return 0
    audit_sealed_block(manifest)
    print("EXECUTION_02 PRE-OUTCOME AUDIT PASS — OUTCOME MAY NOW BE OPENED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
