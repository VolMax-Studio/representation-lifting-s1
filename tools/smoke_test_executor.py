#!/usr/bin/env python3
"""
tools/smoke_test_executor.py
Active API smoke test for representation-lifting-s1 pinned executors:
- Primary: Anthropic claude-sonnet-4-6
- Replication: OpenAI gpt-5.6-sol
Executes real minimal HTTP requests using frozen sampling parameters in tools/executor_config.json to verify:
1. Valid API credentials
2. HTTP 200 OK
3. Exact returned model identity match (returned_id == pinned_model_id)
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

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "executor_config.json")
RECEIPT_PATH = os.path.join(os.path.dirname(__file__), "smoke_test_receipt.json")

def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def test_endpoint(model_id: str, spec: dict) -> dict:
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
        payload = {
            "model": spec["pinned_model_id"],
            "max_tokens": 10,
            "temperature": spec["sampling_parameters"]["temperature"],
            "messages": [{"role": "user", "content": "Respond with 1."}]
        }
    else:
        headers["Authorization"] = f"Bearer {key}"
        payload = {
            "model": spec["pinned_model_id"],
            "max_tokens": 10,
            "temperature": spec["sampling_parameters"]["temperature"],
            "messages": [{"role": "user", "content": "Respond with 1."}]
        }
        
    data = json.dumps(payload).encode("utf-8")
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
            
            # Require exact model ID equality (no fuzzy prefix or alias fallback)
            model_matched = (returned_id == spec["pinned_model_id"])
            record["verified_accessible"] = (resp.status == 200) and model_matched
            if resp.status == 200 and not model_matched:
                record["error"] = f"MODEL_ID_MISMATCH: Pinned '{spec['pinned_model_id']}', but endpoint returned '{returned_id}'."
    except urllib.error.HTTPError as e:
        record["http_status"] = e.code
        record["error"] = f"HTTPError {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}"
    except Exception as e:
        record["error"] = f"{type(e).__name__}: {str(e)}"
        
    return record

def run_smoke_tests() -> bool:
    print("=" * 60)
    print("representation-lifting-s1: LIVE PRE-FREEZE API SMOKE TEST")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)
    
    config = load_config()
    models = config["pinned_models"]
    
    results = {}
    all_passed = True
    
    for model_key in ["claude-sonnet-4-6", "gpt-5.6-sol"]:
        spec = models[model_key]
        print(f"\n[PROBING] {spec['provider']} -> {spec['pinned_model_id']} ({spec['endpoint']})...")
        res = test_endpoint(model_key, spec)
        results[model_key] = res
        
        status_str = "PASS" if res["verified_accessible"] else "FAIL"
        print(f"  Result: {status_str}")
        print(f"  HTTP Status: {res['http_status']}")
        print(f"  Returned Model ID: {res['returned_model_id']}")
        print(f"  Round-trip Latency: {res['latency_ms']} ms")
        if res["error"]:
            print(f"  Diagnostic: {res['error']}")
            all_passed = False
        else:
            print("  Access verified and certified.")
            
    receipt = {
        "schema_version": "v0.5",
        "receipt_type": "hash_addressed_execution_receipt",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "all_endpoints_verified": all_passed,
        "results": results
    }
    
    with open(RECEIPT_PATH, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2)
        f.write("\n")
        
    print("\n" + "=" * 60)
    print(f"Receipt written to: {RECEIPT_PATH}")
    if all_passed:
        print("ALL PINNED EXECUTOR ENDPOINTS VERIFIED ACCESSIBLE.")
        return True
    else:
        print("PRE-FREEZE SMOKE TEST FAILED CLOSED: One or more models unavailable or credentials missing.")
        return False

if __name__ == "__main__":
    success = run_smoke_tests()
    sys.exit(0 if success else 1)
