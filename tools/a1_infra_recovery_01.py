#!/usr/bin/env python3
"""One-shot Gate 5 recovery authorized only by INFRA_RECOVERY_01."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import a1_surface_bridge as bridge


DEFAULT_RECOVERY_CONFIG = (
    ROOT / "evidence" / "amendment_a1" / "INFRA_RECOVERY_01_CONFIG.json"
)
RECOVERY_CONFIG_RELATIVE_PATH = "evidence/amendment_a1/INFRA_RECOVERY_01_CONFIG.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def require_bound_file(root: Path, binding: dict) -> Path:
    path = root / binding["path"]
    actual = sha256_file(path)
    if actual != binding["sha256"]:
        raise RuntimeError(
            f"HASH_MISMATCH:{binding['path']}:expected={binding['sha256']}:actual={actual}"
        )
    return path


def verify_preserved_failed_gate5(root: Path, recovery_config: dict) -> None:
    evidence_root = root / recovery_config["failed_gate5_evidence_root"]
    expected = recovery_config["failed_gate5_evidence_sha256"]
    actual_files = {
        path.relative_to(evidence_root).as_posix()
        for path in evidence_root.rglob("*") if path.is_file()
    }
    if actual_files != set(expected):
        raise RuntimeError("FAILED_GATE5_EVIDENCE_FILESET_MISMATCH")
    for relative_path, expected_sha in sorted(expected.items()):
        actual_sha = sha256_file(evidence_root / relative_path)
        if actual_sha != expected_sha:
            raise RuntimeError(
                f"FAILED_GATE5_EVIDENCE_HASH_MISMATCH:{relative_path}"
            )


def load_bound_runtime(root: Path, recovery_config: dict) -> tuple[dict, dict]:
    a1_path = require_bound_file(root, recovery_config["a1_transport_config"])
    executor_path = require_bound_file(root, recovery_config["frozen_executor_config"])
    require_bound_file(root, recovery_config["frozen_executor_harness"])
    require_bound_file(root, recovery_config["ratified_bridge"])
    require_bound_file(root, recovery_config["recovery_implementation"])
    require_bound_file(root, recovery_config["recovery_tests"])
    require_bound_file(root, recovery_config["recovery_amendment"])
    a1_config = load_json(a1_path)
    executor_config = load_json(executor_path)
    if not isinstance(executor_config.get("transport_policy"), dict):
        raise RuntimeError("FROZEN_EXECUTOR_TRANSPORT_POLICY_MISSING")
    return a1_config, executor_config


def recovery_artifact_dir(root: Path, recovery_config: dict) -> Path:
    amendment_root = (root / "evidence" / "amendment_a1").resolve()
    candidate = (root / recovery_config["recovery_gate5_evidence_root"]).resolve()
    failed = (root / recovery_config["failed_gate5_evidence_root"]).resolve()
    if os.path.commonpath([str(candidate), str(amendment_root)]) != str(amendment_root):
        raise RuntimeError("RECOVERY_NAMESPACE_ESCAPES_AMENDMENT_ROOT")
    if candidate == failed or os.path.commonpath([str(candidate), str(failed)]) == str(failed):
        raise RuntimeError("RECOVERY_NAMESPACE_OVERLAPS_FAILED_GATE5")
    return candidate


def verify_recovery_ratification(root: Path, recovery_config: dict) -> str:
    tag = recovery_config["required_ratification_tag"]
    subprocess.run(
        ["git", "verify-tag", tag], cwd=root, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    tag_commit = subprocess.run(
        ["git", "rev-parse", f"{tag}^{{}}"], cwd=root, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    head_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    if tag_commit != head_commit:
        raise RuntimeError(
            f"RECOVERY_RATIFICATION_TAG_NOT_AT_HEAD:tag={tag_commit}:head={head_commit}"
        )
    return tag_commit


def verify_signed_tree_files(root: Path, recovery_config: dict, tag_commit: str) -> None:
    """Require critical worktree bytes to equal the exact signed commit tree."""
    relative_paths = [
        RECOVERY_CONFIG_RELATIVE_PATH,
        recovery_config["recovery_implementation"]["path"],
        recovery_config["recovery_tests"]["path"],
        recovery_config["recovery_amendment"]["path"],
        recovery_config["a1_transport_config"]["path"],
        recovery_config["ratified_bridge"]["path"],
        recovery_config["frozen_executor_config"]["path"],
        recovery_config["frozen_executor_harness"]["path"],
    ]
    for relative_path in relative_paths:
        try:
            committed = subprocess.run(
                ["git", "show", f"{tag_commit}:{relative_path}"],
                cwd=root, check=True, capture_output=True,
            ).stdout
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"SIGNED_TREE_PATH_MISSING:{relative_path}") from exc
        worktree_path = root / relative_path
        if not worktree_path.is_file() or worktree_path.read_bytes() != committed:
            raise RuntimeError(f"SIGNED_TREE_WORKTREE_MISMATCH:{relative_path}")


def run_recovery_probe(
    a1_config: dict,
    executor_config: dict,
    artifact_dir: Path,
    root: Path,
) -> dict:
    """Pass the already-frozen executor config unchanged into the Gate 5 call path."""
    return bridge.run_gate5_probe(
        model_id="claude-sonnet-4-6",
        a1_config=a1_config,
        artifact_dir=str(artifact_dir),
        config=executor_config,
        root_dir=str(root),
        skip_preflight=False,
    )


def execute_once(root: Path, recovery_config: dict) -> dict:
    verify_preserved_failed_gate5(root, recovery_config)
    a1_config, executor_config = load_bound_runtime(root, recovery_config)
    artifact_dir = recovery_artifact_dir(root, recovery_config)
    if artifact_dir.exists():
        raise RuntimeError("RECOVERY_GATE5_ALREADY_STARTED_OR_COMPLETED")
    ratified_commit = verify_recovery_ratification(root, recovery_config)
    verify_signed_tree_files(root, recovery_config, ratified_commit)

    artifact_dir.mkdir(parents=True, exist_ok=False)
    start_record = {
        "schema_version": "representation-lifting-infra-recovery-start/v1",
        "amendment": "INFRA_RECOVERY_01",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "ratified_commit": ratified_commit,
        "ratification_tag": recovery_config["required_ratification_tag"],
        "maximum_recovery_executions": 1,
    }
    with (artifact_dir / "RECOVERY_STARTED.json").open("x", encoding="utf-8") as stream:
        json.dump(start_record, stream, indent=2, sort_keys=True)
        stream.write("\n")

    return run_recovery_probe(a1_config, executor_config, artifact_dir, root)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="One-shot INFRA_RECOVERY_01 Gate 5")
    parser.add_argument("--execute-recovery-gate5", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute_recovery_gate5:
        parser.print_help()
        return 2
    recovery_config = load_json(DEFAULT_RECOVERY_CONFIG)
    result = execute_once(ROOT, recovery_config)
    if result.get("gate5_pass") is True:
        print("RECOVERY GATE5 PASS")
        return 0
    print("RECOVERY GATE5 HALT")
    return 1


if __name__ == "__main__":
    sys.exit(main())
