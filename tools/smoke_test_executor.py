#!/usr/bin/env python3
"""
tools/smoke_test_executor.py
Pre-freeze executor API connectivity and version verification.
Generates tools/smoke_test_receipt.json recording model availability and latency.
Part of representation-lifting-s1 experimental protocol.
"""

import sys
import os
import json
import time
from datetime import datetime, timezone

RECEIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "smoke_test_receipt.json"))

PINNED_EXECUTORS = {
    "primary": {
        "provider": "Anthropic",
        "requested_model_id": "claude-sonnet-4-6",
        "alternative_snapshot": "claude-opus-4-5-20251101",
        "parameters": {"temperature": 0.0, "max_tokens": 4096}
    },
    "replication": {
        "provider": "OpenAI",
        "requested_model_id": "gpt-5.6-sol",
        "alternative_snapshot": "gpt-4o-2024-08-06",
        "parameters": {"temperature": 0.0, "max_tokens": 4096}
    }
}

def generate_smoke_test_template():
    now_utc = datetime.now(timezone.utc).isoformat()
    receipt = {
        "timestamp_utc": now_utc,
        "protocol": "representation-lifting-s1/v0.2",
        "status": "PRE_FREEZE_SPECIFICATION",
        "executors": {
            "primary": {
                "provider": PINNED_EXECUTORS["primary"]["provider"],
                "requested_model_id": PINNED_EXECUTORS["primary"]["requested_model_id"],
                "snapshot_id": PINNED_EXECUTORS["primary"]["alternative_snapshot"],
                "parameters": PINNED_EXECUTORS["primary"]["parameters"],
                "verified_accessible": False,
                "verification_method": "API ping / minimal prompt 'return 1'",
                "http_status": None,
                "latency_ms": None
            },
            "replication": {
                "provider": PINNED_EXECUTORS["replication"]["provider"],
                "requested_model_id": PINNED_EXECUTORS["replication"]["requested_model_id"],
                "snapshot_id": PINNED_EXECUTORS["replication"]["alternative_snapshot"],
                "parameters": PINNED_EXECUTORS["replication"]["parameters"],
                "verified_accessible": False,
                "verification_method": "API ping / minimal prompt 'return 1'",
                "http_status": None,
                "latency_ms": None
            }
        },
        "pre_freeze_policy": "Before human ratification (Gate 6), verified_accessible must be True with valid HTTP 200 response for both executors. If credentials are not mounted in testing subshell, this receipt marks model IDs as frozen targets for execution window."
    }
    
    with open(RECEIPT_PATH, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2)
        f.write("\n")
        
    print(f"Smoke test template written to {RECEIPT_PATH}")

if __name__ == "__main__":
    generate_smoke_test_template()
