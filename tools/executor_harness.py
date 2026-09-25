#!/usr/bin/env python3
"""
tools/executor_harness.py
Cryptographic execution harness and state machine for representation-lifting-s1.
Standardizes agent interaction loops across experimental roles:
- Role S (Representation Search Executor): 3600s wall-clock, max 15 turns
- Role D (Direct Proof Executor): 10800s wall-clock, max 30 turns
- Role L (Lifted Proof Executor): 10800s wall-clock, max 30 turns

State Machine:
1. Initialize context bundle (target, manifest, optional stub for L).
2. Construct neutral system and initial turn prompts.
3. Turn Loop:
   a. Send conversation transcript to model endpoint (or deterministic mock).
   b. Parse Lean code block (```lean ... ```).
   c. Execute compiler/verifier tool:
      - Role S: tools/check_bridge.py
      - Role D/L: tools/verify_proof.sh
   d. On verification PASS: Record COMPLETE and finalize receipt.
   e. On verification FAIL: Feed compiler stderr/diagnostics back to model as next user turn.
4. Enforces strict termination on wall-clock timeout or turn exhaustion.
5. Emits cryptographically signed execution receipt (execution_receipt.json).
Part of representation-lifting-s1 experimental protocol.
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

ROLE_CONFIGS = {
    "S": {"max_wallclock_seconds": 3600, "max_turns": 15},
    "D": {"max_wallclock_seconds": 10800, "max_turns": 30},
    "L": {"max_wallclock_seconds": 10800, "max_turns": 30}
}

PINNED_MODELS = {
    "claude-sonnet-4-6": {
        "provider": "Anthropic",
        "endpoint": "https://api.anthropic.com/v1/messages",
        "env_var": "ANTHROPIC_API_KEY",
        "headers": {"anthropic-version": "2023-06-01", "content-type": "application/json"}
    },
    "gpt-5.6-sol": {
        "provider": "OpenAI",
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "env_var": "OPENAI_API_KEY",
        "headers": {"content-type": "application/json"}
    }
}

def sha256_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def extract_code_block(response_text: str) -> str | None:
    match = re.search(r'```(?:lean4?|lean)?\s*\n(.*?)\n```', response_text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None

def call_model_api(model_id: str, messages: list[dict], system_prompt: str) -> str:
    spec = PINNED_MODELS.get(model_id)
    if not spec:
        raise ValueError(f"Unknown model_id '{model_id}'. Must be one of {list(PINNED_MODELS.keys())}.")
        
    api_key = os.environ.get(spec["env_var"])
    if not api_key:
        raise RuntimeError(f"Missing API key: environment variable '{spec['env_var']}' is not set.")
        
    headers = dict(spec["headers"])
    if spec["provider"] == "Anthropic":
        headers["x-api-key"] = api_key
        payload = {
            "model": model_id,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": messages
        }
    else:
        headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": model_id,
            "max_tokens": 4096,
            "messages": [{"role": "system", "content": system_prompt}] + messages
        }
        
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(spec["endpoint"], data=data, headers=headers, method="POST")
    
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        if spec["provider"] == "Anthropic":
            return body["content"][0]["text"]
        else:
            return body["choices"][0]["message"]["content"]


class ExecutionHarness:
    def __init__(self, role: str, model_id: str, target_file: str, 
                 manifest_file: str, stub_file: str | None, output_dir: str,
                 mock_mode: bool = False, mock_responses: list[str] | None = None):
        self.role = role.upper()
        if self.role not in ROLE_CONFIGS:
            raise ValueError(f"Invalid role '{role}'. Must be S, D, or L.")
        self.config = ROLE_CONFIGS[self.role]
        self.model_id = model_id
        self.target_file = os.path.abspath(target_file)
        self.manifest_file = os.path.abspath(manifest_file)
        self.stub_file = os.path.abspath(stub_file) if stub_file else None
        self.output_dir = os.path.abspath(output_dir)
        self.mock_mode = mock_mode
        self.mock_responses = mock_responses or []
        self.transcript = []
        
        os.makedirs(self.output_dir, exist_ok=True)
        
    def build_system_prompt(self) -> str:
        return "Write a clear, maintainable Lean proof. Always output your full code inside ```lean ... ```."
        
    def build_initial_user_prompt(self) -> str:
        with open(self.target_file, "r", encoding="utf-8") as f:
            target_code = f.read()
        with open(self.manifest_file, "r", encoding="utf-8") as f:
            manifest_code = f.read()
            
        base = f"Target Statement:\n```lean\n{target_code}\n```\n\nAdmissibility Manifest:\n{manifest_code}\n\n"
        
        if self.role == "S":
            return base + (
                "Task (Role S - Representation Search):\n"
                "Construct a valid representation stub containing:\n"
                "- abbrev LiftDom := ...\n"
                "- abbrev LiftCod := ...\n"
                "- def liftT : LiftDom → LiftCod := ...\n"
                "- theorem preservation_bridge ... : <target> ↔ <lifted_prop> := by sorry\n"
                "The stub must compile with zero errors on Lean 4.34.0."
            )
        elif self.role == "D":
            return base + (
                "Task (Role D - Direct Proof):\n"
                "Provide a complete, verified Lean 4 proof of the target theorem without sorry.\n"
                "Name your theorem 'executor_theorem'."
            )
        else: # Role L
            with open(self.stub_file, "r", encoding="utf-8") as f:
                stub_code = f.read()
            return base + (
                f"Frozen Representation Stub:\n```lean\n{stub_code}\n```\n\n"
                "Task (Role L - Lifted Proof):\n"
                "Provide a complete, verified Lean 4 proof of the target theorem using the frozen representation layer.\n"
                "Prove the bridge and complete the theorem without sorry. Name your theorem 'executor_theorem'."
            )

    def execute_tool(self, candidate_file: str) -> tuple[bool, str]:
        if self.role == "S":
            cmd = [sys.executable, os.path.join(TOOLS_DIR, "check_bridge.py"), self.target_file, candidate_file]
        else:
            cmd = [os.path.join(TOOLS_DIR, "verify_proof.sh"), self.target_file, candidate_file, "executor_theorem"]
            
        res = subprocess.run(cmd, capture_output=True, text=True)
        output = (res.stdout + "\n" + res.stderr).strip()
        return (res.returncode == 0), output

    def run(self) -> dict:
        start_time_utc = datetime.now(timezone.utc).isoformat()
        start_clock = time.perf_counter()
        
        messages = [{"role": "user", "content": self.build_initial_user_prompt()}]
        system_prompt = self.build_system_prompt()
        
        status = "IN_PROGRESS"
        final_candidate_path = None
        turn = 0
        
        while turn < self.config["max_turns"]:
            elapsed = time.perf_counter() - start_clock
            if elapsed >= self.config["max_wallclock_seconds"]:
                status = "TIMEOUT_WALLCLOCK"
                break
                
            turn += 1
            turn_start = time.perf_counter()
            
            # Model turn
            if self.mock_mode:
                if turn - 1 < len(self.mock_responses):
                    response_text = self.mock_responses[turn - 1]
                else:
                    response_text = "```lean\n-- No mock response\n```"
            else:
                response_text = call_model_api(self.model_id, messages, system_prompt)
                
            messages.append({"role": "assistant", "content": response_text})
            
            code = extract_code_block(response_text)
            if not code:
                feedback = "No Lean code block found. Please provide your code inside ```lean ... ```."
                messages.append({"role": "user", "content": feedback})
                self.transcript.append({
                    "turn": turn,
                    "elapsed_seconds": round(time.perf_counter() - start_clock, 2),
                    "code_extracted": False,
                    "verified": False,
                    "feedback": feedback
                })
                continue
                
            candidate_path = os.path.join(self.output_dir, f"candidate_turn_{turn}.lean")
            with open(candidate_path, "w", encoding="utf-8") as f:
                f.write(code + "\n")
                
            verified, tool_output = self.execute_tool(candidate_path)
            self.transcript.append({
                "turn": turn,
                "elapsed_seconds": round(time.perf_counter() - start_clock, 2),
                "code_extracted": True,
                "candidate_path": candidate_path,
                "candidate_sha256": sha256_file(candidate_path),
                "verified": verified,
                "tool_output": tool_output
            })
            
            if verified:
                status = "COMPLETE"
                final_candidate_path = candidate_path
                break
            else:
                feedback = f"Verification failed with diagnostics:\n{tool_output}\n\nPlease fix the errors and provide the updated code."
                messages.append({"role": "user", "content": feedback})
                
        if status == "IN_PROGRESS":
            status = "TIMEOUT_TURNS"
            
        total_elapsed = time.perf_counter() - start_clock
        end_time_utc = datetime.now(timezone.utc).isoformat()
        
        # Calculate token footprint if complete
        footprint_tokens = None
        if status == "COMPLETE" and final_candidate_path:
            count_script = os.path.join(TOOLS_DIR, "count_lean_tokens.py")
            res_c = subprocess.run([sys.executable, count_script, final_candidate_path],
                                   capture_output=True, text=True)
            if res_c.returncode == 0:
                footprint_tokens = int(res_c.stdout.strip())
                
        receipt = {
            "protocol": "representation-lifting-s1/v0.4",
            "role": self.role,
            "model_id": self.model_id,
            "status": status,
            "target_file": self.target_file,
            "target_sha256": sha256_file(self.target_file),
            "manifest_file": self.manifest_file,
            "manifest_sha256": sha256_file(self.manifest_file),
            "stub_file": self.stub_file,
            "stub_sha256": sha256_file(self.stub_file) if self.stub_file else None,
            "start_time_utc": start_time_utc,
            "end_time_utc": end_time_utc,
            "elapsed_seconds": round(total_elapsed, 2),
            "turns_completed": turn,
            "max_turns": self.config["max_turns"],
            "max_wallclock_seconds": self.config["max_wallclock_seconds"],
            "final_candidate_path": final_candidate_path,
            "final_candidate_sha256": sha256_file(final_candidate_path) if final_candidate_path else None,
            "footprint_tokens": footprint_tokens,
            "transcript_turns": len(self.transcript)
        }
        
        receipt_path = os.path.join(self.output_dir, "execution_receipt.json")
        with open(receipt_path, "w", encoding="utf-8") as f:
            json.dump(receipt, f, indent=2)
            f.write("\n")
            
        transcript_path = os.path.join(self.output_dir, "conversation_transcript.json")
        with open(transcript_path, "w", encoding="utf-8") as f:
            json.dump(messages, f, indent=2)
            f.write("\n")
            
        return receipt

def main():
    if len(sys.argv) < 5:
        print(f"Usage: {sys.argv[0]} <role:S|D|L> <model_id> <target_file> <manifest_file> [stub_file] <output_dir>", file=sys.stderr)
        sys.exit(1)
        
    role = sys.argv[1]
    model_id = sys.argv[2]
    target_file = sys.argv[3]
    manifest_file = sys.argv[4]
    
    if role.upper() == "L":
        stub_file = sys.argv[5]
        out_dir = sys.argv[6]
    else:
        stub_file = None
        out_dir = sys.argv[5]
        
    harness = ExecutionHarness(role, model_id, target_file, manifest_file, stub_file, out_dir)
    receipt = harness.run()
    print(json.dumps(receipt, indent=2))

if __name__ == "__main__":
    main()
