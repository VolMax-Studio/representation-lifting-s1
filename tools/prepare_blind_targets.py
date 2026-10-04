#!/usr/bin/env python3
"""
tools/prepare_blind_targets.py
Deterministic extractor for Gate 4 selected ProofNet cases into frozen_target format.
Transforms canonical ProofNet statement into Lake-compatible target module:
- Preserves hoisted imports, opens, and helper definitions.
- Renames main theorem declaration to `theorem frozen_target`.
- Appends `:= by sorry` for baseline elaboration.
"""

import os
import sys
import re
import json
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
sys.path.insert(0, SCRIPT_DIR)

from extract_proofnet_statement import extract_canonical_statement

DEFAULT_JSONL = "/home/volmax-studio/volmax-projects/iot2/ARCHIVE_EXTERNAL/ProofNet-Verified/data/proofnet-verified.jsonl"

FROZEN_CASES = [
    (108, "proofnet-108"),
    (83,  "proofnet-083"),
    (267, "proofnet-267"),
]

def prepare_targets(jsonl_path: str, out_dir: str) -> dict[str, str]:
    if not os.path.isfile(jsonl_path):
        raise FileNotFoundError(f"Source JSONL dataset not found at {jsonl_path}")

    with open(jsonl_path, "r", encoding="utf-8") as f:
        entries = [json.loads(line) for line in f if line.strip()]

    os.makedirs(out_dir, exist_ok=True)
    results = {}

    for idx, case_id in FROZEN_CASES:
        matching = [e for e in entries if e.get("index") == idx]
        if len(matching) != 1:
            raise ValueError(f"Expected exactly 1 entry for index {idx}, got {len(matching)}")
        entry = matching[0]
        name = entry["name"]
        stmt = extract_canonical_statement(entry)

        pattern = r'^(theorem|lemma)\s+' + re.escape(name) + r'\b'
        subbed = re.sub(pattern, r'theorem frozen_target', stmt, flags=re.MULTILINE)
        if "theorem frozen_target" not in subbed:
            raise ValueError(f"Substitution of declaration name failed for {case_id} ({name})")

        target_code = subbed.rstrip() + " := by sorry\n"
        out_path = os.path.join(out_dir, f"{case_id}.lean")
        with open(out_path, "w", encoding="utf-8") as out_f:
            out_f.write(target_code)
        results[case_id] = out_path

    return results

def main():
    parser = argparse.ArgumentParser(description="Prepare deterministic blind targets.")
    parser.add_argument("--jsonl", default=DEFAULT_JSONL, help="Path to proofnet-verified.jsonl")
    parser.add_argument("--out-dir", default=os.path.join(PROJECT_ROOT, "targets"), help="Output directory")
    args = parser.parse_args()

    results = prepare_targets(args.jsonl, args.out_dir)
    for cid, path in results.items():
        print(f"Emitted {cid} -> {path}")

if __name__ == "__main__":
    main()
