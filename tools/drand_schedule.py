#!/usr/bin/env python3
"""
tools/drand_schedule.py
Deterministic scheduling of strictly future drand quicknet rounds.
Part of the representation-lifting-s1 experimental protocol.
"""

import sys

GENESIS_TIME = 1692803367  # quicknet genesis timestamp (Unix seconds)
PERIOD_SECONDS = 3         # quicknet period (3 seconds)
FUTURE_DELAY_SECONDS = 600 # mandatory safety gap between pool publish and drand round (10 minutes)

def round_time(r: int, genesis: int = GENESIS_TIME, period: int = PERIOD_SECONDS) -> int:
    """Returns the exact Unix timestamp when round r was/will be published."""
    return genesis + (r - 1) * period

def compute_scheduled_round(t_pub: int, delay: int = FUTURE_DELAY_SECONDS,
                            genesis: int = GENESIS_TIME, period: int = PERIOD_SECONDS) -> int:
    """
    Computes the first drand round strictly after u = t_pub + delay.
    Formula: r_scheduled = floor((u - genesis) / period) + 2
    
    Invariant guaranteed:
      round_time(r - 1) <= u < round_time(r)
    """
    u = t_pub + delay
    r = ((u - genesis) // period) + 2
    
    # Assert structural invariant
    t_prev = round_time(r - 1, genesis, period)
    t_curr = round_time(r, genesis, period)
    assert t_prev <= u < t_curr, f"Invariant violation: not ({t_prev} <= {u} < {t_curr})"
    
    return r

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <t_pool_publish_unix_timestamp> [delay_seconds]", file=sys.stderr)
        sys.exit(1)
        
    t_pub = int(sys.argv[1])
    delay = int(sys.argv[2]) if len(sys.argv) > 2 else FUTURE_DELAY_SECONDS
    r = compute_scheduled_round(t_pub, delay)
    t_round = round_time(r)
    print(f"Scheduled Round: {r}")
    print(f"Round Publication Time (Unix): {t_round}")
    print(f"Lead Time Over Publish: {t_round - t_pub} seconds (delay requirement: {delay}s)")

if __name__ == "__main__":
    main()
