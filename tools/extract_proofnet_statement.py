#!/usr/bin/env python3
r"""
tools/extract_proofnet_statement.py
Anchored, fail-closed extraction of canonical theorem declarations from ProofNet-Verified JSONL.
Part of the representation-lifting-s1 experimental protocol (v0.20).

Input contract:
- ProofNet-Verified JSONL entry must contain 'name', 'header', and 'formal_stmt'.
- 'formal_stmt' must contain exactly one occurrence of 'sorry'.
- The single 'sorry' must be part of an anchored trailing proof-placeholder pattern:
    r":=\s*(?:by\s*)?sorry\s*$"
- Stripped declaration is assembled as:
    [hoisted import lines]
    [header non-import lines]
    [helper definitions, if any]
    [stripped declaration without proof body]
- Fails closed (raises InputContractError / exit 2) on any contract ambiguity or formatting anomaly.
"""

import sys
import os
import re
import json

import hashlib

PROOFNET_CANONICAL_REPO = "https://github.com/marcusm117/ProofNet-Verified.git"
PROOFNET_CANONICAL_COMMIT = "160414332dc196583f6c37c310b420d2a3b07c58"
PROOFNET_CANONICAL_JSONL_SHA256 = "381f4a06548a4ff6d9b923633c94a97b9c70f41033e13023aae31e1161b7f142"
PROOFNET_TOTAL_ENTRIES = 367

class InputContractError(ValueError):
    """Raised when a candidate input violates the frozen pre-execution contract."""
    pass

PROOF_PLACEHOLDER_PATTERN = re.compile(r":=\s*(?:by\s*)?sorry\s*$", re.DOTALL)

def compute_case_id(index: int) -> str:
    """Computes unambiguous, zero-padded case_id: proofnet-001 through proofnet-367."""
    return f"proofnet-{index:03d}"

def extract_canonical_statement(entry: dict) -> str:
    """
    Extracts a clean, elaborable Lean 4 declaration snippet from a ProofNet JSONL entry.
    Strips the trailing proof placeholder so that the declaration is ready for
    nontriviality tactic probing or proof exploration.
    """
    if not isinstance(entry, dict):
        raise InputContractError("ProofNet entry must be a dictionary.")

    name = entry.get("name")
    if not name or not isinstance(name, str):
        raise InputContractError("ProofNet entry missing valid string 'name'.")

    formal_stmt = entry.get("formal_stmt")
    if not formal_stmt or not isinstance(formal_stmt, str):
        raise InputContractError(f"ProofNet entry '{name}' missing valid string 'formal_stmt'.")

    # Fail-closed check 1: exactly one 'sorry' in formal_stmt
    sorry_count = formal_stmt.count("sorry")
    if sorry_count != 1:
        raise InputContractError(
            f"ProofNet entry '{name}' must contain exactly one 'sorry', but found {sorry_count}."
        )

    # Fail-closed check 2: anchored match at the exact end of formal_stmt
    match = PROOF_PLACEHOLDER_PATTERN.search(formal_stmt)
    if not match:
        raise InputContractError(
            f"ProofNet entry '{name}' formal_stmt does not end with recognized proof placeholder (':= by sorry' or ':= sorry')."
        )

    # Fail-closed check 3: confirm no remaining 'sorry' in the prefix
    stripped_decl = formal_stmt[:match.start()].rstrip()
    if "sorry" in stripped_decl:
        raise InputContractError(
            f"ProofNet entry '{name}' contains 'sorry' outside of trailing proof placeholder."
        )

    header = entry.get("header", "")
    helper = entry.get("helper", "")

    # Collect and hoist all imports to the very top
    raw_text = f"{header}\n\n{helper}\n\n{stripped_decl}"
    import_lines = []
    body_lines = []

    for line in raw_text.splitlines():
        if re.match(r"^\s*import\b", line):
            cleaned_imp = re.sub(r"^\s*", "", line).strip()
            if cleaned_imp not in import_lines:
                import_lines.append(cleaned_imp)
        else:
            body_lines.append(line)

    # Ensure Mathlib is imported if not present
    if "import Mathlib" not in import_lines:
        import_lines.insert(0, "import Mathlib")

    # Reassemble with imports at the top
    assembled_header = "\n".join(import_lines)
    assembled_body = "\n".join(body_lines).strip()

    return f"{assembled_header}\n\n{assembled_body}\n"

def main():
    if len(sys.argv) < 2:
        print("Usage: extract_proofnet_statement.py <proofnet.jsonl> [index_or_name] [output_file]", file=sys.stderr)
        sys.exit(2)

    jsonl_path = sys.argv[1]
    if not os.path.isfile(jsonl_path):
        print(f"INPUT_ERROR: File not found: {jsonl_path}", file=sys.stderr)
        sys.exit(2)

    with open(jsonl_path, "r", encoding="utf-8") as f:
        entries = [json.loads(line) for line in f if line.strip()]

    if len(sys.argv) == 2:
        # Full validation mode across all 367 entries
        print(f"Validating ProofNet dataset against canonical protocol pin...")
        with open(jsonl_path, "rb") as bf:
            file_bytes = bf.read()
        file_sha = hashlib.sha256(file_bytes).hexdigest()
        if file_sha != PROOFNET_CANONICAL_JSONL_SHA256:
            print(
                f"INPUT_ERROR: ProofNet JSONL SHA-256 mismatch!\n"
                f"  Expected: {PROOFNET_CANONICAL_JSONL_SHA256}\n"
                f"  Actual:   {file_sha}",
                file=sys.stderr
            )
            sys.exit(2)

        if len(entries) != PROOFNET_TOTAL_ENTRIES:
            print(
                f"INPUT_ERROR: Expected {PROOFNET_TOTAL_ENTRIES} entries, found {len(entries)} in {jsonl_path}.",
                file=sys.stderr
            )
            sys.exit(2)

        seen_indices = set()
        seen_case_ids = set()
        extracted_count = 0

        for entry_idx, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                print(f"INPUT_ERROR: Row {entry_idx} is not a valid JSON dictionary.", file=sys.stderr)
                sys.exit(2)

            idx = entry.get("index")
            if not isinstance(idx, int) or idx <= 0:
                print(f"INPUT_ERROR: Row {entry_idx} has invalid or missing 'index': {idx}", file=sys.stderr)
                sys.exit(2)

            if idx in seen_indices:
                print(f"INPUT_ERROR: Duplicate index {idx} in {jsonl_path}.", file=sys.stderr)
                sys.exit(2)
            seen_indices.add(idx)

            cid = compute_case_id(idx)
            if cid in seen_case_ids:
                print(f"INPUT_ERROR: Duplicate case_id {cid} in {jsonl_path}.", file=sys.stderr)
                sys.exit(2)
            seen_case_ids.add(cid)

            try:
                stmt = extract_canonical_statement(entry)
            except InputContractError as err:
                print(f"INPUT_ERROR: Extraction failed for row {entry_idx} (index {idx}, name {entry.get('name')}): {err}", file=sys.stderr)
                sys.exit(2)

            if not stmt.startswith("import Mathlib"):
                print(f"INPUT_ERROR: Statement for index {idx} does not start with 'import Mathlib'.", file=sys.stderr)
                sys.exit(2)

            if "sorry" in stmt:
                print(f"INPUT_ERROR: Leaked 'sorry' detected in extracted statement for index {idx}.", file=sys.stderr)
                sys.exit(2)

            extracted_count += 1

        print(
            f"VALIDATED PROOFNET DATASET:\n"
            f"  File:           {jsonl_path}\n"
            f"  SHA-256:        {file_sha} (MATCHES PINNED COMMIT {PROOFNET_CANONICAL_COMMIT})\n"
            f"  Total entries:  {extracted_count}/{PROOFNET_TOTAL_ENTRIES}\n"
            f"  Unique cases:   {len(seen_case_ids)} unique case_ids ({compute_case_id(1)} .. {compute_case_id(PROOFNET_TOTAL_ENTRIES)})\n"
            f"  Extraction:     All {extracted_count} canonical declarations extracted cleanly\n"
            f"  Leaked sorry:   0 across entire dataset\n"
            f"  Status:         PASS"
        )
        sys.exit(0)

    target_key = sys.argv[2]
    matched_entry = None

    if target_key.startswith("proofnet-"):
        # Explicit case_id lookup (e.g. proofnet-168)
        try:
            target_idx = int(target_key.split("-")[1])
        except (ValueError, IndexError):
            print(f"INPUT_ERROR: Malformed case_id '{target_key}'. Expected format 'proofnet-NNN'.", file=sys.stderr)
            sys.exit(2)
        for e in entries:
            if e.get("index") == target_idx:
                matched_entry = e
                break
    elif target_key.isdigit():
        # Explicit integer index lookup (e.g. 168)
        target_idx = int(target_key)
        for e in entries:
            if e.get("index") == target_idx:
                matched_entry = e
                break
    else:
        # Lookup by source_name (e.g. Artin_exercise_2_2_9 or Rudin_exercise_4_8a)
        matching_entries = [e for e in entries if e.get("name") == target_key]
        if len(matching_entries) > 1:
            indices = [e.get("index") for e in matching_entries]
            case_ids = [compute_case_id(i) for i in indices if isinstance(i, int)]
            print(
                f"INPUT_ERROR: Ambiguous source_name '{target_key}' matches {len(matching_entries)} entries "
                f"(indices {indices}, case_ids {case_ids}). "
                f"Specify unique case_id (e.g. '{case_ids[0]}') or numeric index to resolve.",
                file=sys.stderr
            )
            sys.exit(2)
        elif len(matching_entries) == 1:
            matched_entry = matching_entries[0]

    if not matched_entry:
        print(f"INPUT_ERROR: Entry '{target_key}' not found in {jsonl_path}.", file=sys.stderr)
        sys.exit(2)

    try:
        extracted = extract_canonical_statement(matched_entry)
    except InputContractError as err:
        print(f"INPUT_ERROR: {err}", file=sys.stderr)
        sys.exit(2)

    if len(sys.argv) >= 4:
        out_path = sys.argv[3]
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(extracted)
        print(f"Extracted '{matched_entry['name']}' ({compute_case_id(matched_entry.get('index', 0))}) to {out_path}")
    else:
        sys.stdout.write(extracted)

if __name__ == "__main__":
    main()
