#!/usr/bin/env python3
"""
tools/executor_harness.py
Cryptographic execution harness and state machine for representation-lifting-s1 (v0.5).
Standardizes agent interaction loops across experimental roles:
- Role S (Representation Search Executor): 3600s wall-clock, max 15 turns
- Role D (Direct Proof Executor): 10800s wall-clock, max 30 turns
- Role L (Lifted Proof Executor): 10800s wall-clock, max 30 turns

State Machine & Governance:
1. Loads frozen parameters from tools/executor_config.json.
2. Enforces pinned Lake environment (lakefile.toml, lean-toolchain, lake-manifest.json).
3. Infrastructure Resiliency & Classification:
   - Max 3 transport attempts per turn (original + 2 retries).
   - Retries only for network/timeout or HTTP 408, 429, 500, 502, 503, 504 with deterministic backoff.
   - Retries do not consume model turns, but consume wall-clock time and are logged in transcript.
   - Fatal HTTP 4xx or attempt exhaustion terminates with status `INFRA_FAILURE` (NOT_EVALUABLE_INFRA).
4. Hard Wall-Clock Enforcement:
   - `remaining = deadline - now`.
   - Subprocess and API timeouts capped by `remaining`.
   - Expiration sets status to `TIMEOUT_WALLCLOCK`.
5. Role L Provenance & Footprint Binding:
   - Role L receives frozen proof-free specification prefix from S.
   - Role L is verified via tools/verify_lifted.sh (asserting transitive dependency on preservation_bridge).
   - W_L evaluates the full assembled artifact: W(frozen_prefix + proved_bridge + target_proof).
6. Emits hash-addressed execution receipt (tools/execution_receipt.json).
Part of representation-lifting-s1 experimental protocol (v0.5).
"""

import sys
import os
import re
import json
import time
import hashlib
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS_DIR = os.path.join(ROOT_DIR, "tools")
CONFIG_PATH = os.path.join(TOOLS_DIR, "executor_config.json")
COUNT_TOKENS_SCRIPT = os.path.join(TOOLS_DIR, "count_lean_tokens.py")
CHECK_BRIDGE_SCRIPT = os.path.join(TOOLS_DIR, "check_bridge.py")
VERIFY_PROOF_SCRIPT = os.path.join(TOOLS_DIR, "verify_proof.sh")
VERIFY_LIFTED_SCRIPT = os.path.join(TOOLS_DIR, "verify_lifted.sh")

def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def sha256_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def extract_code_block(response_text: str) -> str | None:
    match = re.search(r'```(?:lean4?|lean)?\s*\n(.*?)\n```', response_text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None

def extract_anthropic_text(body: dict) -> tuple[str, str | None]:
    stop_reason = body.get("stop_reason")
    content = body.get("content", [])
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            return block.get("text", ""), stop_reason
    return "", stop_reason

def extract_openai_text(body: dict) -> tuple[str, str | None]:
    choices = body.get("choices", [])
    if choices:
        choice = choices[0]
        stop_reason = choice.get("finish_reason")
        text = choice.get("message", {}).get("content", "")
        return text, stop_reason
    return "", None

def call_model_api_with_resilience(
    model_id: str,
    messages: list[dict],
    system_prompt: str,
    remaining_wallclock: float,
    config: dict,
    transcript: list[dict]
) -> tuple[str, str | None, bool]:
    """
    Returns (response_text, stop_reason, is_infra_failure)
    """
    pinned_models = config["pinned_models"]
    spec = pinned_models.get(model_id)
    if not spec:
        raise ValueError(f"Unknown model_id '{model_id}'.")
        
    api_key = os.environ.get(spec["env_var"])
    if not api_key:
        transcript.append({"event": "infra_error", "detail": f"Environment variable '{spec['env_var']}' not set."})
        return "", None, True

    policy = config["transport_policy"]
    max_attempts = policy["max_attempts_per_turn"]
    retryable_codes = policy["retryable_http_codes"]
    backoffs = policy["backoff_seconds"]
    base_timeout = policy["request_timeout_seconds"]

    headers = dict(spec["headers"])
    if spec["provider"] == "Anthropic":
        headers["x-api-key"] = api_key
        payload = {
            "model": spec["pinned_model_id"],
            "max_tokens": spec["sampling_parameters"]["max_tokens"],
            "temperature": spec["sampling_parameters"]["temperature"],
            "system": system_prompt,
            "messages": messages
        }
    else:
        headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": spec["pinned_model_id"],
            "max_tokens": spec["sampling_parameters"]["max_tokens"],
            "temperature": spec["sampling_parameters"]["temperature"],
            "messages": [{"role": "system", "content": system_prompt}] + messages
        }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(spec["endpoint"], data=data, headers=headers, method="POST")

    for attempt in range(1, max_attempts + 1):
        if remaining_wallclock <= 1.0:
            transcript.append({"event": "timeout_wallclock_pre_request", "attempt": attempt})
            return "", "timeout_wallclock", False

        timeout = min(base_timeout, max(1.0, remaining_wallclock))
        transcript.append({"event": "api_request_start", "attempt": attempt, "timeout_seconds": timeout})

        try:
            start_t = time.perf_counter()
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                elapsed = time.perf_counter() - start_t
                body = json.loads(resp.read().decode("utf-8"))
                returned_id = body.get("model")
                if returned_id != spec["pinned_model_id"]:
                    transcript.append({"event": "model_id_mismatch", "expected": spec["pinned_model_id"], "returned": returned_id})
                    return "", None, True

                if spec["provider"] == "Anthropic":
                    text, stop_reason = extract_anthropic_text(body)
                else:
                    text, stop_reason = extract_openai_text(body)

                transcript.append({
                    "event": "api_request_success",
                    "attempt": attempt,
                    "elapsed_seconds": round(elapsed, 2),
                    "stop_reason": stop_reason
                })
                return text, stop_reason, False

        except urllib.error.HTTPError as e:
            transcript.append({"event": "api_http_error", "attempt": attempt, "code": e.code, "msg": str(e)})
            if e.code in retryable_codes and attempt < max_attempts:
                wait_time = backoffs[attempt - 1] if attempt - 1 < len(backoffs) else 15
                time.sleep(wait_time)
                continue
            return "", None, True

        except (urllib.error.URLError, TimeoutError, OSError) as e:
            transcript.append({"event": "api_network_error", "attempt": attempt, "msg": str(e)})
            if attempt < max_attempts:
                wait_time = backoffs[attempt - 1] if attempt - 1 < len(backoffs) else 15
                time.sleep(wait_time)
                continue
            return "", None, True

    return "", None, True

def count_tokens(text: str) -> int:
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False) as f:
        f.write(text)
        tmp_name = f.name
    try:
        res = subprocess.run([sys.executable, COUNT_TOKENS_SCRIPT, tmp_name], capture_output=True, text=True, check=True)
        return int(res.stdout.strip())
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)

class ExecutorStateMachine:
    def __init__(
        self,
        role: str,
        target_path: str,
        manifest_path: str,
        model_id: str,
        frozen_prefix_path: str | None = None,
        mock_generator=None
    ):
        self.config = load_config()
        self.role = role
        if self.role not in self.config["roles"]:
            raise ValueError(f"Unknown role '{self.role}'. Must be S, D, or L.")
            
        self.target_path = os.path.abspath(target_path)
        self.manifest_path = os.path.abspath(manifest_path)
        self.frozen_prefix_path = os.path.abspath(frozen_prefix_path) if frozen_prefix_path else None
        self.model_id = model_id
        self.mock_generator = mock_generator

        role_cfg = self.config["roles"][self.role]
        self.max_wallclock = role_cfg["max_wallclock_seconds"]
        self.max_turns = role_cfg["max_turns"]
        
        self.transcript = []
        self.receipt = {}

    def run(self) -> dict:
        start_time = time.time()
        deadline = start_time + self.max_wallclock

        with open(self.target_path, "r", encoding="utf-8") as f:
            target_content = f.read()
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            manifest_content = f.read()

        frozen_prefix_content = ""
        if self.frozen_prefix_path:
            with open(self.frozen_prefix_path, "r", encoding="utf-8") as f:
                frozen_prefix_content = f.read()

        # Construct System Prompt
        system_prompt = (
            f"You are Lean 4 Autonomous Executor Role {self.role}.\n"
            "Produce fully elaborable, verified Lean 4 code inside a single ```lean ... ``` code block.\n"
            "Do NOT use 'sorry', 'admit', 'native_decide', or custom unproved axioms.\n"
        )
        if self.role == "S":
            system_prompt += (
                "Goal: Discover representation types (LiftDom, LiftCod), representation map (liftT), "
                "invariant, and proof-free BridgeProp specification property.\n"
                "Format requirement:\n"
                "abbrev LiftDom := ...\n"
                "abbrev LiftCod := ...\n"
                "def liftT : LiftDom → LiftCod := ...\n"
                "def invariant : LiftCod → ... := ...\n"
                "def BridgeProp : Prop := ∀ ..., target_lhs ↔ lifted_rhs\n"
            )
        elif self.role == "D":
            system_prompt += "Goal: Prove the literal target theorem directly as `executor_theorem`.\n"
        elif self.role == "L":
            system_prompt += (
                "Goal: Given the immutable frozen representation prefix, prove `preservation_bridge : BridgeProp` "
                "and prove `executor_theorem` such that executor_theorem transitively uses preservation_bridge.\n"
            )

        # Initial turn prompt
        initial_user_prompt = f"TARGET THEOREM:\n```lean\n{target_content}\n```\n\nADMISSIBILITY MANIFEST:\n{manifest_content}\n"
        if self.role == "L":
            initial_user_prompt += f"\nFROZEN REPRESENTATION PREFIX:\n```lean\n{frozen_prefix_content}\n```\n"

        messages = [{"role": "user", "content": initial_user_prompt}]
        turn = 0
        final_status = "MAX_TURNS_EXHAUSTED"
        verified_code = None
        verified_footprint = None

        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            candidate_file = os.path.join(tmp_dir, "candidate.lean")

            while turn < self.max_turns:
                turn += 1
                now = time.time()
                remaining_wallclock = deadline - now
                if remaining_wallclock <= 0:
                    final_status = "TIMEOUT_WALLCLOCK"
                    break

                self.transcript.append({"event": "turn_start", "turn": turn, "remaining_seconds": round(remaining_wallclock, 2)})

                if self.mock_generator:
                    response_text, stop_reason, infra_fail = self.mock_generator(self.role, turn, messages)
                else:
                    response_text, stop_reason, infra_fail = call_model_api_with_resilience(
                        self.model_id, messages, system_prompt, remaining_wallclock, self.config, self.transcript
                    )

                if infra_fail:
                    final_status = "INFRA_FAILURE"
                    break

                messages.append({"role": "assistant", "content": response_text})
                code = extract_code_block(response_text)

                if not code:
                    diagnostic = "ERROR: No ```lean code block found in response. Please output your Lean code enclosed in ```lean ... ```."
                    messages.append({"role": "user", "content": diagnostic})
                    self.transcript.append({"event": "no_code_block", "turn": turn})
                    continue

                with open(candidate_file, "w", encoding="utf-8") as f:
                    f.write(code)

                candidate_hash = sha256_text(code)
                self.transcript.append({"event": "candidate_authored", "turn": turn, "sha256": candidate_hash})

                # Verification Step
                ver_ok = False
                ver_msg = ""
                proc_timeout = min(300, max(1, int(deadline - time.time())))

                if self.role == "S":
                    try:
                        res = subprocess.run(
                            [sys.executable, CHECK_BRIDGE_SCRIPT, self.target_path, candidate_file],
                            capture_output=True, text=True, timeout=proc_timeout
                        )
                        ver_ok = (res.returncode == 0) and ("CHECK_BRIDGE_SENTINEL_OK" in res.stdout or "BRIDGE_VALID" in res.stdout)
                        ver_msg = (res.stdout + "\n" + res.stderr).strip()
                    except subprocess.TimeoutExpired:
                        ver_ok = False
                        ver_msg = "TIMEOUT: Lean checker exceeded turn time limit."

                elif self.role == "D":
                    try:
                        res = subprocess.run(
                            [VERIFY_PROOF_SCRIPT, self.target_path, candidate_file, "executor_theorem"],
                            capture_output=True, text=True, timeout=proc_timeout
                        )
                        ver_ok = (res.returncode == 0) and ("VERIFICATION_SUCCESS" in res.stdout)
                        ver_msg = (res.stdout + "\n" + res.stderr).strip()
                    except subprocess.TimeoutExpired:
                        ver_ok = False
                        ver_msg = "TIMEOUT: Lean verifier exceeded turn time limit."

                elif self.role == "L":
                    try:
                        res = subprocess.run(
                            [VERIFY_LIFTED_SCRIPT, self.target_path, self.frozen_prefix_path, candidate_file, "executor_theorem"],
                            capture_output=True, text=True, timeout=proc_timeout
                        )
                        ver_ok = (res.returncode == 0) and ("VERIFY_LIFTED_SENTINEL_OK" in res.stdout)
                        ver_msg = (res.stdout + "\n" + res.stderr).strip()
                    except subprocess.TimeoutExpired:
                        ver_ok = False
                        ver_msg = "TIMEOUT: Lean lifted verifier exceeded turn time limit."

                if ver_ok:
                    final_status = "COMPLETE"
                    verified_code = code
                    if self.role == "L":
                        # Bound metric: Full assembled artifact
                        assembled = frozen_prefix_content + "\n\n" + code
                        verified_footprint = count_tokens(assembled)
                    else:
                        verified_footprint = count_tokens(code)

                    self.transcript.append({
                        "event": "verification_passed",
                        "turn": turn,
                        "footprint_tokens": verified_footprint
                    })
                    break
                else:
                    self.transcript.append({
                        "event": "verification_failed",
                        "turn": turn,
                        "diagnostic": ver_msg[:300]
                    })
                    user_feedback = f"LEAN COMPILER / VERIFICATION FEEDBACK:\n{ver_msg}\n\nPlease revise your proof to fix these errors."
                    messages.append({"role": "user", "content": user_feedback})

        elapsed = time.time() - start_time
        self.receipt = {
            "schema_version": "v0.5",
            "receipt_type": "hash_addressed_execution_receipt",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "role": self.role,
            "model_id": self.model_id,
            "target_sha256": sha256_file(self.target_path),
            "manifest_sha256": sha256_file(self.manifest_path),
            "frozen_prefix_sha256": sha256_file(self.frozen_prefix_path) if self.frozen_prefix_path else None,
            "final_status": final_status,
            "turns_consumed": turn,
            "wallclock_seconds": round(elapsed, 2),
            "verified_footprint_tokens": verified_footprint,
            "transcript_summary": self.transcript
        }

        receipt_file = os.path.join(TOOLS_DIR, f"execution_receipt_{self.role.lower()}.json")
        with open(receipt_file, "w", encoding="utf-8") as f:
            json.dump(self.receipt, f, indent=2)

        return self.receipt

def main():
    if len(sys.argv) < 5:
        print(f"Usage: {sys.argv[0]} <role:S|D|L> <target_file> <manifest_file> <model_id> [frozen_prefix_file]", file=sys.stderr)
        sys.exit(1)
        
    role = sys.argv[1].upper()
    target_path = sys.argv[2]
    manifest_path = sys.argv[3]
    model_id = sys.argv[4]
    frozen_prefix = sys.argv[5] if len(sys.argv) > 5 else None
    
    state_machine = ExecutorStateMachine(role, target_path, manifest_path, model_id, frozen_prefix)
    receipt = state_machine.run()
    
    print(f"\nExecution Finished. Status: {receipt['final_status']}")
    print(f"Turns: {receipt['turns_consumed']}, Elapsed: {receipt['wallclock_seconds']}s")
    if receipt["verified_footprint_tokens"] is not None:
        print(f"Verified Footprint Tokens: {receipt['verified_footprint_tokens']}")
    
    sys.exit(0 if receipt["final_status"] == "COMPLETE" else 1)

if __name__ == "__main__":
    main()
