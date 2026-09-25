#!/usr/bin/env python3
"""
tests/test_drand_schedule.py
Regression tests for deterministic drand future-round scheduling.
Verifies boundary conditions, synthetic parameters, and structural invariants.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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

if __name__ == "__main__":
    test_synthetic_parameters()
    test_exact_boundary_conditions()
    test_quicknet_known_round()
    test_invariant_grid()
    print("ALL DRAND SCHEDULE REGRESSION TESTS PASSED.")
