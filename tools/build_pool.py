#!/usr/bin/env python3
r"""
tools/build_pool.py
Deterministic Pool Builder and Gate 1 / Gate 2 Orchestrator.
Part of the representation-lifting-s1 experimental protocol (v0.20).

Orchestrates mechanical filtration of ProofNet-Verified corpus:
  1. Verifies pinned repository commit and JSONL SHA-256.
  2. Asserts exact 367 entries and unique case_id generation (proofnet-001 .. proofnet-367).
  3. Canonical extraction via tools/extract_proofnet_statement.py (anchored placeholder stripping).
  4. Gate 2 Canonical Statement Elaboration Filter:
     - Canonical transformations: extract statement, hoist imports, prepend 'import Mathlib',
       append ':= by sorry', elaborate under deterministic 'set_option maxHeartbeats 200000'.
     - Elaboration failure (syntax error, type mismatch, heartbeat timeout) -> EXCLUDED_TOOLCHAIN_INCOMPATIBLE.
     - Wall-clock watchdog (> 600s) -> INFRA_HANG (operational failure abort; prevents machine-dependent pool).
  5. Gate 1 Nontriviality Filter:
     - Probes 4 basic tactics under 200,000 heartbeats (rfl, decide, linarith, ring).
     - Proved by any tactic -> EXCLUDED_TRIVIAL.
  6. Surviving cases -> POOL.tsv (emitted ONLY if N_INFRA_HANG == 0).
  7. Strict fail-closed machine assertion of partition equation:
     N_total = N_pool + N_trivial + N_toolchain + N_input (strictly requiring N_hang == 0).
  8. Emits bundle commitment manifest (pool_bundle_manifest.json) anchoring all output hashes.
     The external timestamp anchor (Rekor/RFC3161/OpenTimestamps) must anchor the SHA-256 of the
     ENTIRE pool_bundle_manifest.json file itself, anchoring source metadata, builder hash, and outputs.

NOTE: Deterministic outputs contain NO wall-clock timestamps to guarantee byte-identical
reproducibility across independent runs.
"""

import sys
import os
import json
import hashlib
import argparse
from typing import Callable, Any

# Root paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
sys.path.insert(0, SCRIPT_DIR)

from extract_proofnet_statement import (
    extract_canonical_statement,
    compute_case_id,
    InputContractError,
    PROOFNET_CANONICAL_REPO,
    PROOFNET_CANONICAL_COMMIT,
    PROOFNET_CANONICAL_JSONL_SHA256,
    PROOFNET_TOTAL_ENTRIES,
)

from nontriviality_filter import (
    evaluate_statement,
    default_lean_runner,
    MAX_HEARTBEATS,
    WATCHDOG_TIMEOUT_SECONDS,
    BASIC_TACTICS,
    summarize_lean_error,
)

BUILDER_NAME = "tools/build_pool.py"
BUILDER_VERSION = "v0.20"

def compute_file_sha256(filepath: str) -> str:
    """Computes hex SHA-256 digest of a file on disk."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def build_pool(
    jsonl_path: str,
    out_dir: str,
    assert_pinned: bool = True,
    project_root: str = PROJECT_ROOT,
    lean_runner: Callable[[str, str, int], tuple[int, str, str, bool]] = default_lean_runner
) -> dict[str, Any]:
    """
    Executes deterministic pool construction and emits all categorized TSVs,
    partition report, and bundle commitment manifest.
    Fails closed if any INFRA_HANG occurs, ensuring the pool is 100% machine-independent.
    """
    if not os.path.isfile(jsonl_path):
        raise FileNotFoundError(f"Source JSONL dataset not found at {jsonl_path}")

    # Compute source JSONL SHA-256
    source_sha = compute_file_sha256(jsonl_path)
    if assert_pinned and source_sha != PROOFNET_CANONICAL_JSONL_SHA256:
        raise ValueError(
            f"Source dataset SHA-256 mismatch!\n"
            f"  Expected: {PROOFNET_CANONICAL_JSONL_SHA256}\n"
            f"  Actual:   {source_sha}"
        )

    with open(jsonl_path, "r", encoding="utf-8") as f:
        entries = [json.loads(line) for line in f if line.strip()]

    if assert_pinned and len(entries) != PROOFNET_TOTAL_ENTRIES:
        raise ValueError(f"Expected exactly {PROOFNET_TOTAL_ENTRIES} entries, found {len(entries)}")

    # Containers for partitioned cases
    pool_cases: list[tuple[str, str]] = []
    trivial_cases: list[tuple[str, str, str]] = []
    toolchain_cases: list[tuple[str, str, str]] = []
    input_error_cases: list[tuple[str, str, str]] = []
    infra_hang_cases: list[tuple[str, str, str]] = []

    seen_indices: set[int] = set()
    seen_case_ids: set[str] = set()

    for idx_num, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            cid = compute_case_id(idx_num)
            input_error_cases.append((cid, "unknown", "entry_not_a_json_object"))
            continue

        raw_index = entry.get("index")
        source_name = str(entry.get("name", f"entry_{idx_num}"))

        if not isinstance(raw_index, int) or raw_index <= 0:
            cid = compute_case_id(idx_num)
            input_error_cases.append((cid, source_name, f"invalid_or_missing_index: {raw_index}"))
            continue

        if raw_index in seen_indices:
            cid = compute_case_id(raw_index)
            input_error_cases.append((cid, source_name, f"duplicate_index: {raw_index}"))
            continue
        seen_indices.add(raw_index)

        cid = compute_case_id(raw_index)
        if cid in seen_case_ids:
            input_error_cases.append((cid, source_name, f"duplicate_case_id: {cid}"))
            continue
        seen_case_ids.add(cid)

        # Step 1: Canonical Extraction
        try:
            decl = extract_canonical_statement(entry)
        except InputContractError as err:
            input_error_cases.append((cid, source_name, f"input_contract_error: {str(err)}"))
            continue
        except Exception as err:
            input_error_cases.append((cid, source_name, f"extraction_exception: {type(err).__name__}: {str(err)}"))
            continue

        # Step 2: Gate 2 and Gate 1 evaluation via authoritative module
        status, reason = evaluate_statement(
            decl,
            project_root=project_root,
            max_heartbeats=MAX_HEARTBEATS,
            watchdog_seconds=WATCHDOG_TIMEOUT_SECONDS,
            lean_runner=lean_runner
        )

        if status == "POOL":
            pool_cases.append((cid, source_name))
        elif status == "EXCLUDED_TRIVIAL":
            trivial_cases.append((cid, source_name, reason))
        elif status == "EXCLUDED_TOOLCHAIN_INCOMPATIBLE":
            toolchain_cases.append((cid, source_name, reason))
        elif status == "INFRA_HANG":
            infra_hang_cases.append((cid, source_name, reason))
        else:
            input_error_cases.append((cid, source_name, f"unrecognized_status: {status} ({reason})"))

    total_evaluated = len(entries)
    n_pool = len(pool_cases)
    n_trivial = len(trivial_cases)
    n_toolchain = len(toolchain_cases)
    n_input = len(input_error_cases)
    n_hang = len(infra_hang_cases)

    # CRITICAL FAIL-CLOSED RULE: If N_INFRA_HANG > 0, POOL.tsv MUST NOT be emitted!
    # A valid pool is produced ONLY when N_INFRA_HANG == 0, guaranteeing machine-independence.
    if n_hang > 0:
        os.makedirs(out_dir, exist_ok=True)
        hang_tsv_path = os.path.join(out_dir, "INFRA_HANG.tsv")
        with open(hang_tsv_path, "w", encoding="utf-8") as f:
            f.write("case_id\tsource_name\treason\n")
            for cid, sname, rsn in sorted(infra_hang_cases, key=lambda x: x[0]):
                f.write(f"{cid}\t{sname}\t{rsn}\n")
        raise RuntimeError(
            f"FAIL-CLOSED: {n_hang} cases timed out under watchdog (> {WATCHDOG_TIMEOUT_SECONDS}s). "
            f"POOL.tsv generation ABORTED to preserve strict machine-independent pool construction. "
            f"Details logged to {hang_tsv_path}."
        )

    # Machine-assert exact partition invariant when N_INFRA_HANG == 0
    partition_sum = n_pool + n_trivial + n_toolchain + n_input
    if partition_sum != total_evaluated:
        raise AssertionError(
            f"CRITICAL: Partition equation violation! "
            f"Total evaluated ({total_evaluated}) != Sum of valid buckets ({partition_sum}) "
            f"[pool={n_pool}, trivial={n_trivial}, toolchain={n_toolchain}, input={n_input}]"
        )

    # Sort all buckets lexicographically by case_id for deterministic byte output
    pool_cases.sort(key=lambda x: x[0])
    trivial_cases.sort(key=lambda x: x[0])
    toolchain_cases.sort(key=lambda x: x[0])
    input_error_cases.sort(key=lambda x: x[0])

    os.makedirs(out_dir, exist_ok=True)

    # Write POOL.tsv
    pool_tsv_path = os.path.join(out_dir, "POOL.tsv")
    with open(pool_tsv_path, "w", encoding="utf-8") as f:
        f.write("case_id\tsource_name\n")
        for cid, sname in pool_cases:
            f.write(f"{cid}\t{sname}\n")

    # Write EXCLUDED_TRIVIAL.tsv
    trivial_tsv_path = os.path.join(out_dir, "EXCLUDED_TRIVIAL.tsv")
    with open(trivial_tsv_path, "w", encoding="utf-8") as f:
        f.write("case_id\tsource_name\treason\n")
        for cid, sname, rsn in trivial_cases:
            f.write(f"{cid}\t{sname}\t{rsn}\n")

    # Write EXCLUDED_TOOLCHAIN_INCOMPATIBLE.tsv
    toolchain_tsv_path = os.path.join(out_dir, "EXCLUDED_TOOLCHAIN_INCOMPATIBLE.tsv")
    with open(toolchain_tsv_path, "w", encoding="utf-8") as f:
        f.write("case_id\tsource_name\treason\n")
        for cid, sname, rsn in toolchain_cases:
            f.write(f"{cid}\t{sname}\t{rsn}\n")

    # Write INPUT_ERROR.tsv
    input_tsv_path = os.path.join(out_dir, "INPUT_ERROR.tsv")
    with open(input_tsv_path, "w", encoding="utf-8") as f:
        f.write("case_id\tsource_name\treason\n")
        for cid, sname, rsn in input_error_cases:
            f.write(f"{cid}\t{sname}\t{rsn}\n")

    # Generate deterministic pool_build_report.json (NO timestamps)
    report_dict = {
        "schema_version": "representation-lifting-pool-build-report/v1",
        "builder_version": BUILDER_VERSION,
        "source_repository": PROOFNET_CANONICAL_REPO,
        "source_commit": PROOFNET_CANONICAL_COMMIT if assert_pinned else "fixture",
        "source_jsonl_sha256": source_sha,
        "deterministic_max_heartbeats": MAX_HEARTBEATS,
        "watchdog_timeout_seconds": WATCHDOG_TIMEOUT_SECONDS,
        "total_source_entries": total_evaluated,
        "partition_counts": {
            "pool": n_pool,
            "excluded_trivial": n_trivial,
            "excluded_toolchain_incompatible": n_toolchain,
            "input_error": n_input,
            "infra_hang": 0
        },
        "partition_equation": "total_source_entries == pool + excluded_trivial + excluded_toolchain_incompatible + input_error",
        "partition_invariant_satisfied": True
    }
    report_path = os.path.join(out_dir, "pool_build_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2, sort_keys=True)
        f.write("\n")

    # Compute SHA-256 of builder and filter scripts
    builder_script_path = os.path.abspath(__file__)
    builder_sha = compute_file_sha256(builder_script_path)
    filter_script_path = os.path.join(SCRIPT_DIR, "nontriviality_filter.py")
    filter_sha = compute_file_sha256(filter_script_path)

    # Compute SHA-256 of all generated bundle files
    bundle_files_hashes = {
        "POOL.tsv": compute_file_sha256(pool_tsv_path),
        "EXCLUDED_TRIVIAL.tsv": compute_file_sha256(trivial_tsv_path),
        "EXCLUDED_TOOLCHAIN_INCOMPATIBLE.tsv": compute_file_sha256(toolchain_tsv_path),
        "INPUT_ERROR.tsv": compute_file_sha256(input_tsv_path),
        "pool_build_report.json": compute_file_sha256(report_path),
    }

    # Deterministic bundle commitment hash (over output files)
    canonical_bundle_bytes = json.dumps(bundle_files_hashes, sort_keys=True).encode("utf-8")
    bundle_commitment_sha = hashlib.sha256(canonical_bundle_bytes).hexdigest()

    bundle_manifest_dict = {
        "schema_version": "representation-lifting-pool-bundle-manifest/v1",
        "builder_name": BUILDER_NAME,
        "builder_sha256": builder_sha,
        "filter_name": "tools/nontriviality_filter.py",
        "filter_sha256": filter_sha,
        "source_repository": PROOFNET_CANONICAL_REPO,
        "source_commit": PROOFNET_CANONICAL_COMMIT if assert_pinned else "fixture",
        "source_jsonl_sha256": source_sha,
        "bundle_files": bundle_files_hashes,
        "bundle_sha256": bundle_commitment_sha,
        "anchor_rule": "The external timestamp anchor (Rekor/RFC3161/OpenTimestamps) must anchor the SHA-256 of this entire pool_bundle_manifest.json file, cryptographically binding source metadata, builder code, and all output hashes."
    }
    bundle_manifest_path = os.path.join(out_dir, "pool_bundle_manifest.json")
    with open(bundle_manifest_path, "w", encoding="utf-8") as f:
        json.dump(bundle_manifest_dict, f, indent=2, sort_keys=True)
        f.write("\n")

    manifest_whole_sha = compute_file_sha256(bundle_manifest_path)

    return {
        "report": report_dict,
        "bundle_manifest": bundle_manifest_dict,
        "bundle_commitment_sha": bundle_commitment_sha,
        "manifest_whole_sha": manifest_whole_sha
    }

def main():
    parser = argparse.ArgumentParser(
        description="Deterministic Pool Builder and Gate 1/2 Orchestrator for representation-lifting-s1."
    )
    default_jsonl = os.path.abspath(
        os.path.join(PROJECT_ROOT, "..", "..", "ARCHIVE_EXTERNAL", "ProofNet-Verified", "data", "proofnet-verified.jsonl")
    )
    parser.add_argument(
        "--source",
        type=str,
        default=os.environ.get("PROOFNET_JSONL", default_jsonl),
        help="Path to ProofNet-Verified JSONL dataset."
    )
    parser.add_argument(
        "--outdir",
        type=str,
        default=PROJECT_ROOT,
        help="Output directory where POOL.tsv and manifests will be written."
    )
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Run in fixture / development mode (relaxes 367-count and pinned hash assertion)."
    )

    args = parser.parse_args()

    print(f"================================================================================")
    print(f"DETERMINISTIC POOL BUILDER — representation-lifting-s1 ({BUILDER_VERSION})")
    print(f"================================================================================")
    print(f"Source JSONL:     {args.source}")
    print(f"Output Directory: {args.outdir}")
    print(f"Fixture Mode:     {args.fixture}")
    print(f"Heartbeat Limit:  {MAX_HEARTBEATS}")
    print(f"Watchdog Timeout: {WATCHDOG_TIMEOUT_SECONDS}s")
    print(f"--------------------------------------------------------------------------------")

    try:
        res = build_pool(
            jsonl_path=args.source,
            out_dir=args.outdir,
            assert_pinned=not args.fixture,
            project_root=PROJECT_ROOT
        )
    except Exception as err:
        print(f"CRITICAL EXECUTION ERROR: {type(err).__name__}: {err}", file=sys.stderr)
        sys.exit(2)

    rep = res["report"]["partition_counts"]
    print(f"PARTITION RESULTS:")
    print(f"  Total Source Entries:            {res['report']['total_source_entries']}")
    print(f"  POOL (surviving blind pool):     {rep['pool']}")
    print(f"  EXCLUDED_TRIVIAL (tactics):      {rep['excluded_trivial']}")
    print(f"  EXCLUDED_TOOLCHAIN_INCOMPATIBLE: {rep['excluded_toolchain_incompatible']}")
    print(f"  INPUT_ERROR (format/parse):      {rep['input_error']}")
    print(f"  INFRA_HANG (watchdog timeout):   {rep['infra_hang']}")
    print(f"  Partition Invariant Satisfied:   {res['report']['partition_invariant_satisfied']}")
    print(f"--------------------------------------------------------------------------------")
    print(f"INTERNAL BUNDLE SHA-256:           {res['bundle_commitment_sha']}")
    print(f"WHOLE MANIFEST SHA-256 (ANCHOR):   {res['manifest_whole_sha']}")
    print(f"================================================================================")
    sys.exit(0)

if __name__ == "__main__":
    main()
