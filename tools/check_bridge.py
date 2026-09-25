#!/usr/bin/env python3
"""
tools/check_bridge.py
Mechanical verification of representation stub:
1. Verifies LiftDom, LiftCod, liftT, and preservation_bridge exist.
2. Evaluates Identity Guard (rejects if LiftDom = LiftCod or liftT = id).
3. Verifies Target Linkage:
   - Compares binder signatures.
   - Requires bridge conclusion to be an equivalence (↔ or Iff).
   - Requires one side to match target conclusion.
   - Requires other side to reference liftT.
   - Rejects unlinked tautologies or extraneous unquantified hypotheses.
Part of the representation-lifting-s1 experimental protocol.
"""

import sys
import re
import os
import subprocess
import tempfile

def parse_binders_and_conclusion(stmt: str) -> tuple[list[str], str]:
    """
    Parses a theorem signature into leading binder tokens and conclusion.
    Example: '(n : ℕ) (hn : 2 ≤ n) : Concl' -> binders: ['(n : ℕ)', '(hn : 2 ≤ n)'], conclusion: 'Concl'
    """
    s = stmt.strip()
    # Strip leading 'theorem name ... :' if present
    if s.startswith("theorem ") or s.startswith("lemma "):
        colon_pos = s.find(":")
        if colon_pos != -1:
            s = s[colon_pos+1:].strip()
            
    binders = []
    i = 0
    n = len(s)
    
    while i < n:
        while i < n and s[i].isspace():
            i += 1
        if i >= n:
            break
        if s[i] in '([{':
            # Binder group
            open_bracket = s[i]
            close_bracket = ')' if open_bracket == '(' else (']' if open_bracket == '[' else '}')
            start = i
            depth = 1
            i += 1
            while i < n and depth > 0:
                if s[i] == open_bracket:
                    depth += 1
                elif s[i] == close_bracket:
                    depth -= 1
                i += 1
            binders.append(s[start:i].strip())
        elif s[i] == ':':
            # Separator between binders and conclusion
            i += 1
            break
        else:
            # Reached conclusion without explicit ':' separator
            break
            
    conclusion = s[i:].strip()
    return binders, conclusion


def check_identity_guard(stub_content: str) -> bool:
    """
    Tests whether LiftDom = LiftCod or liftT = id is definitionally true.
    Returns True if trivial (GUARD ACTIVATED -> REJECT).
    Returns False if non-trivial (PASS).
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = os.path.join(tmp_dir, "IdentityTest.lean")
        # Build check: try example : LiftDom = LiftCod := rfl
        content = f"""
{stub_content}

-- Test definitional equality of domain and codomain
example : LiftDom = LiftCod := rfl
"""
        with open(test_file, "w") as f:
            f.write(content)
            
        res = subprocess.run(["lake", "env", "lean", test_file],
                             capture_output=True, text=True)
        if res.returncode == 0:
            # LiftDom = LiftCod compiled cleanly -> trivial domain lift!
            return True
            
        # Test if liftT = id
        test_file_id = os.path.join(tmp_dir, "IdentityTestId.lean")
        content_id = f"""
{stub_content}

-- Test definitional equality of liftT to identity
example : liftT = id := rfl
"""
        with open(test_file_id, "w") as f:
            f.write(content_id)
        res_id = subprocess.run(["lake", "env", "lean", test_file_id],
                                capture_output=True, text=True)
        if res_id.returncode == 0:
            # liftT = id compiled cleanly -> identity lift!
            return True

    return False


def verify_target_linkage(target_stmt: str, stub_content: str) -> tuple[bool, str]:
    """
    Verifies that preservation_bridge is structurally linked to target_stmt.
    """
    # 1. Check required structural declarations
    for req in ["LiftDom", "LiftCod", "liftT", "preservation_bridge"]:
        if req not in stub_content:
            return False, f"MISSING_DECLARATION: Stub does not declare {req}"
            
    # 2. Extract preservation_bridge declaration line
    match = re.search(r'theorem\s+(preservation_bridge\w*)\s*(.*?):=\s*by\s+sorry',
                      stub_content, re.DOTALL)
    if not match:
        return False, "INVALID_BRIDGE_SYNTAX: Cannot find 'theorem preservation_bridge ... := by sorry'"
        
    bridge_sig = match.group(2).strip()
    
    target_binders, target_concl = parse_binders_and_conclusion(target_stmt)
    bridge_binders, bridge_concl = parse_binders_and_conclusion(bridge_sig)
    
    # 3. Binder check: bridge cannot introduce extra unquantified hypotheses
    # Normalize binders by stripping variable names: '(n : ℕ)' -> ': ℕ'
    def norm_binders(binders):
        normed = []
        for b in binders:
            b_clean = re.sub(r'^[([{]\s*[a-zA-Z0-9_α-ωΑ-Ω\']+\s*:\s*', ': ', b)
            normed.append(b_clean.strip(' )]}'))
        return normed

    if norm_binders(bridge_binders) != norm_binders(target_binders):
        return False, f"EXTRA_HYPOTHESIS: Bridge binders {bridge_binders} do not match target binders {target_binders}"
        
    # 4. Equivalence check: bridge conclusion must be an Iff (↔)
    if "↔" in bridge_concl:
        parts = bridge_concl.split("↔", 1)
    elif "<->" in bridge_concl:
        parts = bridge_concl.split("<->", 1)
    elif bridge_concl.startswith("Iff "):
        # e.g. Iff LHS RHS
        rest = bridge_concl[4:].strip()
        parts = rest.split(None, 1)
    else:
        return False, "NON_EQUIVALENCE_BRIDGE: Bridge conclusion must be an equivalence (↔)"
        
    lhs = parts[0].strip()
    rhs = parts[1].strip()
    
    # Clean whitespace and parentheses for comparison
    def clean_expr(e):
        e = re.sub(r'\s+', ' ', e)
        if e.startswith("(") and e.endswith(")"):
            e = e[1:-1].strip()
        return e

    clean_lhs = clean_expr(lhs)
    clean_rhs = clean_expr(rhs)
    clean_target = clean_expr(target_concl)
    
    # 5. Tautology check
    if clean_lhs == clean_rhs:
        return False, "TAUTOLOGICAL_BRIDGE: Bridge equivalence is of the form P ↔ P"
        
    # 6. Target match check: one side must match target conclusion
    target_matched = (clean_lhs == clean_target) or (clean_rhs == clean_target)
    if not target_matched:
        return False, f"UNLINKED_TARGET: Neither bridge side matches target conclusion '{clean_target}'"
        
    # 7. liftT reference check: the other side must reference liftT
    lifted_side = clean_rhs if clean_lhs == clean_target else clean_lhs
    if "liftT" not in lifted_side:
        return False, "UNLIFTED_BRIDGE: The non-target side of the bridge does not reference 'liftT'"
        
    return True, "LINKAGE_VERIFIED"


def check_bridge(target_stmt_file: str, stub_file: str) -> tuple[bool, str]:
    with open(target_stmt_file, "r") as f:
        target_stmt = f.read().strip()
    with open(stub_file, "r") as f:
        stub_content = f.read()
        
    # 1. Structural linkage check
    ok, reason = verify_target_linkage(target_stmt, stub_content)
    if not ok:
        return False, reason
        
    # 2. Identity guard check
    is_trivial = check_identity_guard(stub_content)
    if is_trivial:
        return False, "IDENTITY_GUARD: Representation domain or mapping is definitionally trivial (id)"
        
    return True, "BRIDGE_VALID"


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <target_stmt_file> <stub_file>", file=sys.stderr)
        sys.exit(1)
        
    target_file = sys.argv[1]
    stub_file = sys.argv[2]
    
    valid, message = check_bridge(target_file, stub_file)
    if valid:
        print(f"PASS: {message}")
        sys.exit(0)
    else:
        print(f"FAIL: {message}")
        sys.exit(1)

if __name__ == "__main__":
    main()
