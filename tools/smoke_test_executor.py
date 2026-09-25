#!/usr/bin/env python3
"""
tools/smoke_test_executor.py
Active API smoke test for representation-lifting-s1 pinned executors:
- Primary: Anthropic claude-sonnet-4-6
- Replication: OpenAI gpt-5.6-sol
Executes real minimal HTTP requests via standard library (urllib.request) to verify:
1. Valid API credentials
2. HTTP 200 OK
3. Returned model identity matches pinned specification
4. Records round-trip latency into tools/smoke_test_receipt.json.
Fail-closed: Returns exit code 1 if either model is inaccessible or unverified.
Part of representation-lifting-s1 experimental protocol.
"""

import sys
import os
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

RECEIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "smoke_test_receipt.json"))

PRIMARY_SPEC = {
    "provider": "Anthropic",
    "pinned_model_id": "claude-sonnet-4-6",
    "endpoint": "https://api.anthropic.com/v1/messages",
    "env_var": "ANTHROPIC_API_KEY",
    "headers": {
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    },
    "payload": {
        "model": "claude-sonnet-4-6",
        "max_tokens": 10,
        "messages": [{"role": "user", "content": "Respond with 1."}]
    }
}

REPLICATION_SPEC = {
    "provider": "OpenAI",
    "pinned_model_id": "gpt-5.6-sol",
    "endpoint": "https://api.openai.com/v1/chat/completions",
    "env_var": "OPENAI_API_KEY",
    "headers": {
        "content-type": "application/json"
    },
    "payload": {
        "model": "gpt-5.6-sol",
        "max_tokens": 10,
        "messages": [{"role": "user", "content": "Respond with 1."}]
    }
}

def test_endpoint(spec: dict) -> dict:
    key = os.environ.get(spec["env_var"])
    record = {
        "provider": spec["provider"],
        "pinned_model_id": spec["pinned_model_id"],
        "verified_accessible": False,
        "http_status": None,
        "returned_model_id": None,
        "latency_ms": None,
        "error": None
    }
    
    if not key:
        record["error"] = f"Environment variable {spec['env_var']} is not set."
        return record
        
    headers = dict(spec["headers"])
    if spec["provider"] == "Anthropic":
        headers["x-api-key"] = key
    else:
        headers["Authorization"] = f"Bearer {key}"
        
    data = json.dumps(spec["payload"]).encode("utf-8")
    req = urllib.request.Request(spec["endpoint"], data=data, headers=headers, method="POST")
    
    start_time = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            latency = (time.perf_counter() - start_time) * 1000
            body = json.loads(resp.read().decode("utf-8"))
            record["http_status"] = resp.status
            record["latency_ms"] = round(latency, 2)
            returned_id = body.get("model")
            record["returned_model_id"] = returned_id
            
            # Require exact model ID or approved provider snapshot prefix
            model_matched = (returned_id == spec["pinned_model_id"]) or (returned_id and returned_id.startswith(spec["pinned_model_id"]))
            record["verified_accessible"] = (resp.status == 200) and model_matched
            if resp.status == 200 and not model_matched:
                record["error"] = f"MODEL_ID_MISMATCH: Pinned '{spec['pinned_model_id']}', but endpoint returned '{returned_id}'."
    except urllib.error.HTTPError as e:
        record["http_status"] = e.code
        record["error"] = f"HTTPError {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}"
    except Exception as e:
        record["error"] = str(e)
        
    return record

def main():
    now_utc = datetime.now(timezone.utc).isoformat()
    primary_res = test_endpoint(PRIMARY_SPEC)
    replication_res = test_endpoint(REPLICATION_SPEC)
    
    receipt = {
        "timestamp_utc": now_utc,
        "protocol": "representation-lifting-s1/v0.4",
        "executors": {
            "primary": primary_res,
            "replication": replication_res
        }
    }
    
    with open(RECEIPT_PATH, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2)
        f.write("\n")
        
    print(f"Receipt written to {RECEIPT_PATH}")
    
    # Gate check: for scientific freeze ratification, credentials must be active
    if primary_res["verified_accessible"] and replication_res["verified_accessible"]:
        print("PASS: Both primary and replication executors successfully verified.")
        sys.exit(0)
    else:
        print("FAIL_CLOSED: Pre-freeze executor smoke test failed. Missing credentials or endpoint error:")
        if not primary_res["verified_accessible"]:
            print(f"  Primary ({PRIMARY_SPEC['pinned_model_id']}): {primary_res['error']}")
        if not replication_res["verified_accessible"]:
            print(f"  Replication ({REPLICATION_SPEC['pinned_model_id']}): {replication_res['error']}")
        sys.exit(1)

if __name__ == "__main__":
    main()
