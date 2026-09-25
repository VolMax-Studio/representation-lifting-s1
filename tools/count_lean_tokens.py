#!/usr/bin/env python3
"""
tools/count_lean_tokens.py
Deterministic Lean 4 source lexical token counter.
Strips imports, whitespace, single-line comments (--), and nested block comments (/- ... -/).
Supports quoted identifiers («...»), unicode operators, and string escape sequences.
Part of the representation-lifting-s1 experimental protocol.
"""

import sys
import re
import unicodedata

def strip_imports_and_comments(source: str) -> str:
    """
    Strips top-level import lines, single-line comments, and arbitrarily nested block comments.
    Preserves string contents exactly so comment markers inside strings are not stripped.
    """
    # 1. Filter out import lines
    lines = source.splitlines()
    filtered_lines = []
    for line in lines:
        if re.match(r'^\s*import\b', line):
            continue
        filtered_lines.append(line)
    text = "\n".join(filtered_lines)

    # 2. State-machine scanner to strip comments while respecting strings and nesting
    out = []
    i = 0
    n = len(text)
    comment_depth = 0
    
    while i < n:
        if comment_depth == 0:
            if text[i] == '"':
                out.append('"')
                i += 1
                while i < n:
                    ch = text[i]
                    out.append(ch)
                    if ch == '\\':
                        i += 1
                        if i < n:
                            out.append(text[i])
                    elif ch == '"':
                        break
                    i += 1
                i += 1
                continue
            
            if text[i:i+2] == '--':
                i += 2
                while i < n and text[i] != '\n':
                    i += 1
                continue
                
            if text[i:i+2] == '/-':
                comment_depth = 1
                i += 2
                continue
                
            out.append(text[i])
            i += 1
        else:
            if text[i:i+2] == '/-':
                comment_depth += 1
                i += 2
            elif text[i:i+2] == '-/':
                comment_depth -= 1
                i += 2
            else:
                i += 1

    return "".join(out)


MULTI_CHAR_OPS = sorted([
    ":=", "::", "->", "→", "<-", "←", "<->", "↔", "=>", "⇒",
    "<=", "≤", ">=", "≥", "!=", "≠", "==", "&&", "||",
    "..", "...", "+=", "-=", "*=", "/=", "++", "|>"
], key=len, reverse=True)

def is_ident_start(ch: str) -> bool:
    if ch == '_':
        return True
    cat = unicodedata.category(ch)
    # Letter categories: Lu, Ll, Lt, Lm, Lo, Nl
    return cat.startswith('L') or cat == 'Nl'

def is_ident_cont(ch: str) -> bool:
    if ch in ("_", "'", "."):
        return True
    cat = unicodedata.category(ch)
    return cat.startswith('L') or cat.startswith('N')


def tokenize_cleaned_source(text: str) -> list[str]:
    """
    Tokenizes cleaned Lean source text into a discrete list of lexical tokens.
    """
    tokens = []
    i = 0
    n = len(text)
    
    while i < n:
        ch = text[i]
        
        # Skip whitespace
        if ch.isspace():
            i += 1
            continue
            
        # 1. Quoted identifier: «...»
        if ch == '«':
            end = text.find('»', i + 1)
            if end != -1:
                tokens.append(text[i:end+1])
                i = end + 1
            else:
                tokens.append(text[i:])
                i = n
            continue
            
        # 2. String literal: "..."
        if ch == '"':
            start = i
            i += 1
            while i < n:
                if text[i] == '\\':
                    i += 2
                elif text[i] == '"':
                    i += 1
                    break
                else:
                    i += 1
            tokens.append(text[start:i])
            continue
            
        # 3. Multi-character operators
        matched_op = None
        for op in MULTI_CHAR_OPS:
            if text.startswith(op, i):
                matched_op = op
                break
        if matched_op:
            tokens.append(matched_op)
            i += len(matched_op)
            continue
            
        # 4. Numbers (decimal or hex/bin)
        if ch.isdigit():
            start = i
            if ch == '0' and i + 1 < n and text[i+1] in 'xXbBoO':
                i += 2
                while i < n and (text[i].isalnum() or text[i] == '_'):
                    i += 1
            else:
                while i < n and (text[i].isdigit() or text[i] == '_'):
                    i += 1
                if i < n and text[i] == '.' and i + 1 < n and text[i+1].isdigit():
                    i += 1
                    while i < n and (text[i].isdigit() or text[i] == '_'):
                        i += 1
            tokens.append(text[start:i])
            continue
            
        # 5. Identifiers / keywords
        if is_ident_start(ch):
            start = i
            i += 1
            while i < n and is_ident_cont(text[i]):
                i += 1
            tokens.append(text[start:i])
            continue
            
        # 6. Single character punctuation / operator / symbol (including unicode math symbols)
        tokens.append(ch)
        i += 1
        
    return tokens


def count_lean_tokens(source: str) -> tuple[int, list[str]]:
    cleaned = strip_imports_and_comments(source)
    tokens = tokenize_cleaned_source(cleaned)
    return len(tokens), tokens


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} [--tokens] <path_to_lean_file>", file=sys.stderr)
        sys.exit(1)
        
    show_tokens = False
    file_path = sys.argv[1]
    if file_path == "--tokens":
        show_tokens = True
        file_path = sys.argv[2]
        
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    count, tokens = count_lean_tokens(content)
    if show_tokens:
        for t in tokens:
            print(t)
    else:
        print(count)

if __name__ == "__main__":
    main()
