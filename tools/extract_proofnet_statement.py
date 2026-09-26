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

class InputContractError(ValueError):
    """Raised when a candidate input violates the frozen pre-execution contract."""
    pass

PROOF_PLACEHOLDER_PATTERN = re.compile(r":=\s*(?:by\s*)?sorry\s*$", re.DOTALL)

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
        print(f"Validated JSONL: {len(entries)} entries found.")
        sys.exit(0)

    target_key = sys.argv[2]
    matched_entry = None
    if target_key.isdigit():
        target_idx = int(target_key)
        for e in entries:
            if e.get("index") == target_idx:
                matched_entry = e
                break
    else:
        for e in entries:
            if e.get("name") == target_key:
                matched_entry = e
                break

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
        print(f"Extracted '{matched_entry['name']}' to {out_path}")
    else:
        sys.stdout.write(extracted)

if __name__ == "__main__":
    main()
