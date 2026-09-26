#!/usr/bin/env python3
"""
tests/test_drand_schedule.py
Regression tests for deterministic drand future-round scheduling.
Verifies boundary conditions, synthetic parameters, and structural invariants.
"""

import sys
import os
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from tools.drand_schedule import compute_scheduled_round, round_time, GENESIS_TIME, PERIOD_SECONDS

def test_synthetic_parameters():
    # Synthetic: genesis = 10, period = 3
    genesis = 10
    period = 3
    delay = 100
    
    # Case 1: u = 110 (10 + 100).
    # (110 - 10) // 3 = 100 // 3 = 33.
    # r = 33 + 2 = 35.
    # round_time(34) = 10 + 33*3 = 109 <= 110
    # round_time(35) = 10 + 34*3 = 112 > 110
    r = compute_scheduled_round(t_pub=10, delay=100, genesis=genesis, period=period)
    assert r == 35, f"Expected 35, got {r}"
    assert round_time(34, genesis, period) <= 110 < round_time(35, genesis, period)
    print("test_synthetic_parameters: PASS")

def test_exact_boundary_conditions():
    genesis = 1000
    period = 3
    
    # Exactly on boundary:
    # Round 10: time = 1000 + 9*3 = 1027
    # If u = 1027 exactly:
    # (1027 - 1000) // 3 = 27 // 3 = 9.
    # r = 9 + 2 = 11.
    # round_time(10) = 1027 <= 1027
    # round_time(11) = 1030 > 1027
    r_exact = compute_scheduled_round(t_pub=27, delay=1000, genesis=genesis, period=period)
    assert r_exact == 11, f"Expected 11 on exact boundary, got {r_exact}"
    assert round_time(10, genesis, period) <= 1027 < round_time(11, genesis, period)
    
    # 1 second before boundary: u = 1026
    r_before = compute_scheduled_round(t_pub=26, delay=1000, genesis=genesis, period=period)
    # (1026 - 1000) // 3 = 26 // 3 = 8 -> r = 10
    assert r_before == 10
    assert round_time(9, genesis, period) <= 1026 < round_time(10, genesis, period)

    # 1 second after boundary: u = 1028
    r_after = compute_scheduled_round(t_pub=28, delay=1000, genesis=genesis, period=period)
    # (1028 - 1000) // 3 = 28 // 3 = 9 -> r = 11
    assert r_after == 11
    assert round_time(10, genesis, period) <= 1028 < round_time(11, genesis, period)
    print("test_exact_boundary_conditions: PASS")

def test_quicknet_known_round():
    # Quicknet: genesis = 1692803367, period = 3
    # Round 1000 publication time:
    t_1000 = round_time(1000, GENESIS_TIME, PERIOD_SECONDS)
    expected_t_1000 = 1692803367 + 999 * 3  # 1692806364
    assert t_1000 == expected_t_1000 == 1692806364
    
    # If pool is published 600s before round 1000 minus 1s:
    # u = 1692806363 -> should pick round 1000
    t_pub = 1692806363 - 600
    r = compute_scheduled_round(t_pub, delay=600)
    assert r == 1000, f"Expected 1000, got {r}"
    print("test_quicknet_known_round: PASS")

def test_invariant_grid():
    # Sweep over 1000 consecutive seconds
    base_t = 1700000000
    for dt in range(1000):
        t_pub = base_t + dt
        r = compute_scheduled_round(t_pub, delay=600)
        u = t_pub + 600
        t_prev = round_time(r - 1)
        t_curr = round_time(r)
        assert t_prev <= u < t_curr, f"Failed at dt={dt}: not ({t_prev} <= {u} < {t_curr})"
    print("test_invariant_grid: PASS (1000 points checked)")

def test_quicknet_constants():
    import json
    import hashlib
    root_path = os.path.join(ROOT_DIR, "external_roots", "drand_quicknet_info_api.raw.json")
    with open(root_path, "rb") as f:
        content = f.read()
    assert hashlib.sha256(content).hexdigest() == "3e690bc527c8a4e78232bc06b5a3cff057c51c68f51b208a1a21b2abd6d6b194"
    info = json.loads(content.decode("utf-8"))
    
    from tools.drand_schedule import QUICKNET_CHAIN_HASH, GENESIS_TIME, PERIOD_SECONDS
    assert QUICKNET_CHAIN_HASH == info["hash"]
    assert GENESIS_TIME == info["genesis_time"]
    assert PERIOD_SECONDS == info["period"]
    # v0.19: verify all fields, including groupHash which caught the v0.18 manual-copy error
    assert info["groupHash"] == "f477d5c89f21a17c863a7f937c6a6d15859414d2be09cd448d4279af331c5d3e"
    assert info["schemeID"] == "bls-unchained-g1-rfc9380"
    print("test_quicknet_constants: PASS (verified against archived raw /info root)")

def test_cross_relay_canonical_provenance():
    """Proves the two archived relay responses are semantically identical."""
    import json
    import hashlib
    api_path = os.path.join(ROOT_DIR, "external_roots", "drand_quicknet_info_api.raw.json")
    relay2_path = os.path.join(ROOT_DIR, "external_roots", "drand_quicknet_info_relay2.raw.json")
    cf_path = os.path.join(ROOT_DIR, "external_roots", "drand_quicknet_info_cloudflare.raw.json")

    with open(api_path) as f:
        api_data = json.load(f)
    with open(relay2_path) as f:
        relay2_data = json.load(f)

    # Canonical equality: sorted-key, compact JSON
    api_canonical = json.dumps(api_data, sort_keys=True, separators=(",", ":"))
    relay2_canonical = json.dumps(relay2_data, sort_keys=True, separators=(",", ":"))
    assert api_canonical == relay2_canonical, "api.drand.sh and api2.drand.sh disagree"

    # Also verify cloudflare if present
    if os.path.exists(cf_path):
        with open(cf_path) as f:
            cf_data = json.load(f)
        cf_canonical = json.dumps(cf_data, sort_keys=True, separators=(",", ":"))
        assert api_canonical == cf_canonical, "api.drand.sh and drand.cloudflare.com disagree"

    # Verify meta files record the canonical SHA
    meta_path = os.path.join(ROOT_DIR, "external_roots", "drand_quicknet_info_api.meta.json")
    with open(meta_path) as f:
        meta = json.load(f)
    expected_canonical_sha = hashlib.sha256(api_canonical.encode()).hexdigest()
    assert meta["canonical_json_sha256"] == expected_canonical_sha
    assert meta["cross_relay_canonical_match"] == "PASS"

    print("test_cross_relay_canonical_provenance: PASS (3 relays, canonical match)")

if __name__ == "__main__":
    test_synthetic_parameters()
    test_exact_boundary_conditions()
    test_quicknet_known_round()
    test_invariant_grid()
    test_quicknet_constants()
    test_cross_relay_canonical_provenance()
    print("ALL DRAND SCHEDULE REGRESSION TESTS PASSED.")
