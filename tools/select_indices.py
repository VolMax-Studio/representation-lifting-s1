#!/usr/bin/env python3
"""
tools/select_indices.py
Deterministic rejection-sampling of blind problem indices from drand quicknet randomness.
Part of the representation-lifting-s1 experimental protocol.
"""

import sys
import hashlib

def select_indices(R: bytes, N: int, count: int = 3) -> list[int]:
    """
    Selects `count` distinct indices in {0, ..., N-1} from 32 raw randomness bytes `R`.
    Uses rejection sampling to ensure zero modulo bias.
    """
    if N < count:
        raise ValueError(f"Pool size N={N} is strictly less than required sample count={count}.")
    
    selected = []
    j = 0
    limit = (2**256) - ((2**256) % N)
    
    while len(selected) < count:
        msg = b"representation-lifting-s1/v0.1\x00" + R + j.to_bytes(8, byteorder="big")
        H_j = hashlib.sha256(msg).digest()
        v_j = int.from_bytes(H_j, byteorder="big")
        j += 1
        
        if v_j >= limit:
            continue
            
        candidate_idx = v_j % N
        if candidate_idx not in selected:
            selected.append(candidate_idx)
            
    return selected

def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <hex_randomness_R_or_sig> <pool_size_N>", file=sys.stderr)
        sys.exit(1)
        
    raw_hex = sys.argv[1].strip()
    # If a full drand signature is passed (typically 48 or 96 bytes hex), take its SHA-256
    sig_bytes = bytes.fromhex(raw_hex)
    if len(sig_bytes) == 32:
        R = sig_bytes
    else:
        R = hashlib.sha256(sig_bytes).digest()
        
    N = int(sys.argv[2])
    indices = select_indices(R, N, count=3)
    for idx in indices:
        print(idx)

if __name__ == "__main__":
    main()
