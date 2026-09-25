#!/usr/bin/env python3
"""
tools/executor_harness.py
Cryptographic execution harness and state machine for representation-lifting-s1 (v0.7).
Standardizes agent interaction loops across experimental roles:
- Role S (Representation Search Executor): 3600s wall-clock, max 15 turns
- Role D (Direct Proof Executor): 10800s wall-clock, max 30 turns
- Role L (Lifted Proof Executor): 10800s wall-clock, max 30 turns

State Machine & Governance (v0.7):
1. Loads frozen parameters from tools/executor_config.json (request_timeout_seconds: 600).
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
5. Method Mode Machine-Readable Enforcement:
   - Evaluates machine-readable deny-list (admissibility/<case>.json) with exact and prefix matching.
   - Verifiers enforce zero references to prohibited terminal constants across all candidate declarations.
6. Role L Structural Proof Architecture:
   - Role L receives frozen prefix defining LiftDom, LiftCod, liftT, LiftedClaim, and BridgeProp.
   - Role L authors ONLY `preservation_bridge : BridgeProp` and `lifted_theorem : LiftedClaim`.
   - Transitive non-circularity: `preservation_bridge ∉ Deps*(lifted_theorem)` is enforced.
   - Trusted verifier mechanically synthesizes `synthesized_target` and audits kernel axioms.
7. Truncation Normalization:
   - Flags responses hitting `max_tokens` / `length` as `OUTPUT_TRUNCATED`.
8. Real Cumulative Multi-Theorem Calibration State Machine (H1):
   - Direct: T1 declarations compiled as immutable frozen prefix + T2 body; W_D(T1+T2) = tokens(D1 + D2).
   - Lifted: Reuses representation core (LiftDom, LiftCod, liftT, invariant) from T1; T2 receives dedicated
     LiftedClaim_T2 and BridgeProp_T2; cumulative artifact is S1 + L1 + S2 + L2.
9. Emits hash-addressed execution receipts.

Part of representation-lifting-s1 experimental protocol (v0.7).
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

def sha256_file(filepath: str | None) -> str | None:
    if not filepath or not os.path.exists(filepath):
        return None
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def resolve_admissibility_json(target_path: str, manifest_path: str | None = None, admissibility_path: str | None = None) -> str | None:
    if admissibility_path and os.path.isfile(admissibility_path):
        return os.path.abspath(admissibility_path)
    if manifest_path and manifest_path.endswith(".json") and os.path.isfile(manifest_path):
        return os.path.abspath(manifest_path)
    base = os.path.basename(target_path).lower()
    for fam in ["fibonacci", "pell", "roots_of_unity"]:
        if fam in base or (manifest_path and fam in os.path.basename(manifest_path).lower()):
            candidate = os.path.join(ROOT_DIR, "admissibility", f"{fam}.json")
            if os.path.isfile(candidate):
                return candidate
    default_cand = os.path.join(ROOT_DIR, "admissibility", "default.json")
    if os.path.isfile(default_cand):
        return default_cand
    return None

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

def is_stop_reason_truncated(stop_reason: str | None) -> bool:
    if not stop_reason:
        return False
    return stop_reason.lower() in ("max_tokens", "length")

def extract_representation_core(s_code: str) -> str:
    """
    Extracts the representation core (LiftDom, LiftCod, liftT, invariant, helpers)
    from a verified Role S stub, omitting problem-specific LiftedClaim and BridgeProp.
    """
    lines = []
    skip = False
    for line in s_code.splitlines():
        if re.match(r'^\s*(?:def|abbrev|theorem|lemma)\s+(?:LiftedClaim|BridgeProp)\b', line):
            skip = True
            continue
        elif skip and re.match(r'^\s*(?:def|abbrev|theorem|lemma)\s+[a-zA-Z0-9_]+', line):
            skip = False
        if not skip:
            lines.append(line)
    return "\n".join(lines).strip()

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

                truncated = is_stop_reason_truncated(stop_reason)
                transcript.append({
                    "event": "api_request_success",
                    "attempt": attempt,
                    "elapsed_seconds": round(elapsed, 2),
                    "stop_reason": stop_reason,
                    "output_truncated": truncated
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
        admissibility_path: str | None = None,
        mock_generator=None,
        additional_context_prompt: str | None = None,
        save_receipt_path: str | None = None
    ):
        self.config = load_config()
        self.role = role
        if self.role not in self.config["roles"]:
            raise ValueError(f"Unknown role '{self.role}'. Must be S, D, or L.")
            
        self.target_path = os.path.abspath(target_path)
        self.manifest_path = os.path.abspath(manifest_path)
        self.frozen_prefix_path = os.path.abspath(frozen_prefix_path) if frozen_prefix_path else None
        self.admissibility_path = resolve_admissibility_json(self.target_path, self.manifest_path, admissibility_path)
        self.model_id = model_id
        self.mock_generator = mock_generator
        self.additional_context_prompt = additional_context_prompt
        self.save_receipt_path = save_receipt_path

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

        # Load Prohibited constants description for prompt
        prohibited_desc = ""
        if self.admissibility_path and os.path.exists(self.admissibility_path):
            with open(self.admissibility_path, "r", encoding="utf-8") as f:
                adm_data = json.load(f)
                prohibited_consts = adm_data.get("prohibited_constants", [])
                if prohibited_consts:
                    prohibited_desc = (
                        "\nMETHOD MODE ADMISSIBILITY RESTRICTIONS (PRIMARY REGIME):\n"
                        "You are STRICTLY FORBIDDEN from directly referencing the following terminal library lemmas:\n"
                        + "\n".join(f"- `{c}`" for c in prohibited_consts) +
                        "\nDirect references to these constants in your code will trigger immediate compilation failure (FORBIDDEN_METHOD_MODE_CONSTANT).\n"
                    )

        # Construct System Prompt
        system_prompt = (
            f"You are Lean 4 Autonomous Executor Role {self.role}.\n"
            "Produce fully elaborable, verified Lean 4 code inside a single ```lean ... ``` code block.\n"
            "Do NOT use 'sorry', 'admit', 'native_decide', or custom unproved axioms.\n"
        )
        if prohibited_desc:
            system_prompt += prohibited_desc

        if self.role == "S":
            system_prompt += (
                "\nRole S Goal: Discover representation types (LiftDom, LiftCod), representation map (liftT), "
                "invariant, LiftedClaim proposition, and proof-free BridgeProp specification property.\n"
                "Format requirement:\n"
                "abbrev LiftDom := ...\n"
                "abbrev LiftCod := ...\n"
                "def liftT : ... := ...\n"
                "def invariant : ... := ...\n"
                "def LiftedClaim : Prop := ...\n"
                "def BridgeProp : Prop := ∀ ..., target ↔ lifted\n"
            )
        elif self.role == "D":
            system_prompt += "\nRole D Goal: Prove the literal target theorem directly as `executor_theorem`.\n"
        elif self.role == "L":
            system_prompt += (
                "\nRole L Goal: Given the immutable frozen representation prefix (which defines LiftDom, LiftCod, "
                "liftT, LiftedClaim, and BridgeProp), prove:\n"
                "1. `preservation_bridge : BridgeProp`\n"
                "2. `lifted_theorem : LiftedClaim`\n"
                "Do NOT write `executor_theorem`. The trusted verifier mechanically synthesizes `executor_theorem`.\n"
                "CRITICAL NON-CIRCULARITY RULE: `lifted_theorem` MUST NOT transitively reference `preservation_bridge`.\n"
            )

        # Initial turn prompt
        initial_user_prompt = f"TARGET THEOREM:\n```lean\n{target_content}\n```\n\nADMISSIBILITY MANIFEST:\n{manifest_content}\n"
        if self.frozen_prefix_path:
            label = "FROZEN REPRESENTATION PREFIX" if self.role in ("L", "S") else "FROZEN CUMULATIVE PREFIX"
            initial_user_prompt += f"\n{label}:\n```lean\n{frozen_prefix_content}\n```\n"
        if self.additional_context_prompt:
            initial_user_prompt += f"\nADDITIONAL CONTEXT / PREVIOUS THEOREMS:\n{self.additional_context_prompt}\n"

        messages = [{"role": "user", "content": initial_user_prompt}]
        turn = 0
        final_status = "MAX_TURNS_EXHAUSTED"
        verified_code = None
        verified_footprint = None
        last_was_truncated = False

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

                last_was_truncated = is_stop_reason_truncated(stop_reason)
                messages.append({"role": "assistant", "content": response_text})
                code = extract_code_block(response_text)

                if not code:
                    diagnostic = "ERROR: No ```lean code block found in response. Please output your Lean code enclosed in ```lean ... ```."
                    messages.append({"role": "user", "content": diagnostic})
                    self.transcript.append({"event": "no_code_block", "turn": turn, "output_truncated": last_was_truncated})
                    continue

                candidate_hash = sha256_text(code)
                self.transcript.append({
                    "event": "candidate_authored",
                    "turn": turn,
                    "sha256": candidate_hash,
                    "output_truncated": last_was_truncated
                })

                # Verification Step
                ver_ok = False
                ver_msg = ""
                proc_timeout = min(300, max(1, int(deadline - time.time())))

                if self.role == "S":
                    # If representation core prefix is present, combine it with candidate code for check_bridge
                    s_to_check = (frozen_prefix_content + "\n\n" + code) if self.frozen_prefix_path else code
                    with open(candidate_file, "w", encoding="utf-8") as f:
                        f.write(s_to_check)

                    try:
                        cmd = [sys.executable, CHECK_BRIDGE_SCRIPT, self.target_path, candidate_file]
                        if self.admissibility_path:
                            cmd.append(self.admissibility_path)
                        res = subprocess.run(cmd, capture_output=True, text=True, timeout=proc_timeout)
                        ver_ok = (res.returncode == 0) and ("CHECK_BRIDGE_SENTINEL_OK" in res.stdout or "BRIDGE_VALID" in res.stdout)
                        ver_msg = (res.stdout + "\n" + res.stderr).strip()
                    except subprocess.TimeoutExpired:
                        ver_ok = False
                        ver_msg = "TIMEOUT: Lean checker exceeded turn time limit."

                elif self.role == "D":
                    with open(candidate_file, "w", encoding="utf-8") as f:
                        f.write(code)

                    try:
                        cmd = [VERIFY_PROOF_SCRIPT, self.target_path, candidate_file, "executor_theorem"]
                        if self.admissibility_path:
                            cmd.append(self.admissibility_path)
                        elif self.frozen_prefix_path:
                            cmd.append("")
                        if self.frozen_prefix_path:
                            cmd.append(self.frozen_prefix_path)
                        res = subprocess.run(cmd, capture_output=True, text=True, timeout=proc_timeout)
                        ver_ok = (res.returncode == 0) and ("VERIFICATION_SUCCESS" in res.stdout)
                        ver_msg = (res.stdout + "\n" + res.stderr).strip()
                    except subprocess.TimeoutExpired:
                        ver_ok = False
                        ver_msg = "TIMEOUT: Lean verifier exceeded turn time limit."

                elif self.role == "L":
                    with open(candidate_file, "w", encoding="utf-8") as f:
                        f.write(code)

                    try:
                        cmd = [VERIFY_LIFTED_SCRIPT, self.target_path, self.frozen_prefix_path, candidate_file]
                        if self.admissibility_path:
                            cmd.append(self.admissibility_path)
                        res = subprocess.run(cmd, capture_output=True, text=True, timeout=proc_timeout)
                        ver_ok = (res.returncode == 0) and ("VERIFY_LIFTED_SENTINEL_OK" in res.stdout)
                        ver_msg = (res.stdout + "\n" + res.stderr).strip()
                    except subprocess.TimeoutExpired:
                        ver_ok = False
                        ver_msg = "TIMEOUT: Lean lifted verifier exceeded turn time limit."

                if ver_ok:
                    final_status = "COMPLETE"
                    verified_code = code
                    if self.role == "L":
                        # Full assembled artifact (frozen prefix + proved bridge + lifted theorem)
                        assembled = frozen_prefix_content + "\n\n" + code
                        verified_footprint = count_tokens(assembled)
                    elif self.role == "D":
                        # Cumulative artifact if frozen prefix exists
                        assembled = (frozen_prefix_content + "\n\n" + code) if self.frozen_prefix_path else code
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
                        "diagnostic": ver_msg[:300],
                        "output_truncated": last_was_truncated
                    })
                    trunc_note = "\nNOTE: Your output was truncated by the token limit. Please make your definitions/proofs more concise." if last_was_truncated else ""
                    user_feedback = f"LEAN COMPILER / VERIFICATION FEEDBACK:\n{ver_msg}{trunc_note}\n\nPlease revise your code to fix these errors."
                    messages.append({"role": "user", "content": user_feedback})

            if final_status == "MAX_TURNS_EXHAUSTED" and last_was_truncated:
                final_status = "OUTPUT_TRUNCATED"

        elapsed = time.time() - start_time
        self.receipt = {
            "schema_version": "representation-lifting-execution-receipt/v1",
            "receipt_type": "hash_addressed_execution_receipt",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "role": self.role,
            "model_id": self.model_id,
            "target_sha256": sha256_file(self.target_path),
            "manifest_sha256": sha256_file(self.manifest_path),
            "admissibility_sha256": sha256_file(self.admissibility_path),
            "frozen_prefix_sha256": sha256_file(self.frozen_prefix_path) if self.frozen_prefix_path else None,
            "final_status": final_status,
            "turns_consumed": turn,
            "wallclock_seconds": round(elapsed, 2),
            "verified_footprint_tokens": verified_footprint,
            "verified_code": verified_code,
            "transcript_summary": self.transcript
        }

        if self.save_receipt_path:
            os.makedirs(os.path.dirname(os.path.abspath(self.save_receipt_path)), exist_ok=True)
            with open(self.save_receipt_path, "w", encoding="utf-8") as f:
                json.dump(self.receipt, f, indent=2)

        return self.receipt

def run_calibration_family(
    family_name: str,
    model_id: str,
    mock_generator=None,
    on_d_complete_callback=None,
    run_tmp_root: str | None = None
) -> dict:
    """
    Executes the sequential multi-theorem calibration state machine (H1):
    1. Branch-Output Non-Persistence Isolation:
       - Purge any stale branch receipts, temp files, or leftover artifacts from prior runs.
       - Hold D proof results exclusively in harness process memory (no persistent D receipt on disk).
       - Eliminate all candidate temp files immediately upon verification completion.
    2. Direct Branch:
       - Run Role D on T1. Record W_D(T1).
       - Compile T1 proof code as frozen prefix for T2.
       - Run Role D on T2. Record cumulative W_D(T1 + T2).
       - Marginal cost: Delta_D^(2) = W_D(T1+T2) - W_D(T1).
    3. Inter-Branch Isolation Boundary:
       - Invoke on_d_complete_callback (if provided) to assert non-persistence of D outputs.
       - Clean up any temporary cumulative prefix files before S/L commencement.
    4. Lifted Branch:
       - Run Role S on T1 -> representation prefix S1.
       - Run Role L on T1 with S1 prefix -> Record W_L(T1) = tokens(S1 + L1).
       - Extract representation core (LiftDom, LiftCod, liftT, invariant).
       - Run Role S on T2 with frozen representation core -> S2 (LiftedClaim_T2, BridgeProp_T2).
       - Run Role L on T2 with reused representation core + L1 helpers + S2 -> L2.
       - Record cumulative W_L(T1 + T2) = tokens(S1 + L1 + S2 + L2).
       - Marginal cost: Delta_L^(2) = W_L(T1+T2) - W_L(T1).
    5. Evaluation of H1 Amortization Dividend & Joint Atomic Receipt:
       - Check: Delta_L^(2) <= 0.50 * Delta_D^(2).
       - Atomically emit joint paired receipt only after both branches have completed.
    """
    import tempfile

    own_tmp_ctx = None
    if not run_tmp_root:
        own_tmp_ctx = tempfile.TemporaryDirectory()
        run_tmp_root = own_tmp_ctx.name

    try:
        # 0. Procedural Branch-Output Non-Persistence Isolation:
        # Purge any stale receipts or outputs from previous executions
        for stale_receipt in [
            os.path.join(TOOLS_DIR, "execution_receipt_d.json"),
            os.path.join(TOOLS_DIR, "execution_receipt_s.json"),
            os.path.join(TOOLS_DIR, "execution_receipt_l.json"),
            os.path.join(TOOLS_DIR, f"execution_receipt_calibration_{family_name}.json"),
            os.path.join(TOOLS_DIR, f"execution_receipt_calibration_{family_name}_{model_id}.json")
        ]:
            if os.path.exists(stale_receipt):
                try:
                    os.remove(stale_receipt)
                except OSError:
                    pass

        t1_path = os.path.join(ROOT_DIR, "calibration", f"{family_name}_t1.lean")
        t2_path = os.path.join(ROOT_DIR, "calibration", f"{family_name}_t2.lean")
        adm_path = os.path.join(ROOT_DIR, "admissibility", f"{family_name}.json")
        manifest_path = adm_path if os.path.exists(adm_path) else os.path.join(ROOT_DIR, "admissibility", "default.json")

        if not os.path.exists(t1_path) or not os.path.exists(t2_path):
            raise FileNotFoundError(f"Calibration targets for family '{family_name}' not found.")

        calib_report = {
            "schema_version": "representation-lifting-execution-receipt/v1",
            "receipt_type": "calibration_family_execution_receipt",
            "family_name": family_name,
            "model_id": model_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "direct": {},
            "lifted": {},
            "marginal_dividend_satisfied": False,
            "cumulative_amortization_satisfied": False,
            "h1_dividend_satisfied": False,
            "ratio_delta_l_over_delta_d": None
        }

        # --- DIRECT BRANCH ---
        sm_d1 = ExecutorStateMachine("D", t1_path, manifest_path, model_id, admissibility_path=adm_path, mock_generator=mock_generator)
        r_d1 = sm_d1.run()
        calib_report["direct"]["d1_status"] = r_d1["final_status"]
        calib_report["direct"]["w_d_t1"] = r_d1["verified_footprint_tokens"]
        d1_code = r_d1.get("verified_code") or ""

        if r_d1["final_status"] == "COMPLETE":
            # Rename executor_theorem -> executor_theorem_t1 in frozen prefix to prevent Lean name collision
            d1_prefix = re.sub(r'\b(theorem|def|lemma)\s+executor_theorem\b', r'\1 executor_theorem_t1', d1_code)
            with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False, dir=run_tmp_root) as f:
                f.write(d1_prefix)
                d1_prefix_file = f.name
            try:
                d_ctx = (
                    "FROZEN CUMULATIVE PREFIX (T1 theorem & helpers):\n"
                    "The previous T1 proof and its helpers are already loaded in the environment as `executor_theorem_t1`.\n"
                    "You may call or reuse them. Author your complete proof for T2 as `executor_theorem`."
                )
                sm_d2 = ExecutorStateMachine("D", t2_path, manifest_path, model_id, frozen_prefix_path=d1_prefix_file, admissibility_path=adm_path, mock_generator=mock_generator, additional_context_prompt=d_ctx)
                r_d2 = sm_d2.run()
                calib_report["direct"]["d2_status"] = r_d2["final_status"]
                calib_report["direct"]["w_d_t1_t2"] = r_d2["verified_footprint_tokens"]

                if r_d2["final_status"] == "COMPLETE":
                    delta_d = max(0, r_d2["verified_footprint_tokens"] - r_d1["verified_footprint_tokens"])
                    calib_report["direct"]["delta_d_2"] = delta_d
                else:
                    delta_d = None
                    calib_report["direct"]["delta_d_2"] = None
            finally:
                if os.path.exists(d1_prefix_file):
                    os.remove(d1_prefix_file)
        else:
            delta_d = None
            calib_report["direct"]["d2_status"] = "SKIPPED_D1_FAILED"
            calib_report["direct"]["w_d_t1_t2"] = None
            calib_report["direct"]["delta_d_2"] = None

        # Inter-Branch Isolation Boundary Hook (asserts D non-persistence before S/L start)
        if on_d_complete_callback:
            on_d_complete_callback(calib_report)

        # --- LIFTED BRANCH ---
        sm_s1 = ExecutorStateMachine("S", t1_path, manifest_path, model_id, admissibility_path=adm_path, mock_generator=mock_generator)
        r_s1 = sm_s1.run()
        calib_report["lifted"]["s1_status"] = r_s1["final_status"]
        s1_code = r_s1.get("verified_code") or ""

        if r_s1["final_status"] == "COMPLETE":
            with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False, dir=run_tmp_root) as f:
                f.write(s1_code)
                s1_file = f.name
            try:
                sm_l1 = ExecutorStateMachine("L", t1_path, manifest_path, model_id, frozen_prefix_path=s1_file, admissibility_path=adm_path, mock_generator=mock_generator)
                r_l1 = sm_l1.run()
                calib_report["lifted"]["l1_status"] = r_l1["final_status"]
                calib_report["lifted"]["w_l_t1"] = r_l1["verified_footprint_tokens"]
                l1_code = r_l1.get("verified_code") or ""

                if r_l1["final_status"] == "COMPLETE":
                    # Reuse ONLY representation core from S1
                    s_core = extract_representation_core(s1_code)
                    with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False, dir=run_tmp_root) as f:
                        f.write(s_core)
                        s_core_file = f.name
                    try:
                        s2_ctx = (
                            "FROZEN REPRESENTATION CORE:\n"
                            "The representation domain, codomain, map, and invariants from T1 are frozen:\n"
                            f"```lean\n{s_core}\n```\n"
                            "Do NOT redefine LiftDom, LiftCod, or liftT. Define new `LiftedClaim` and `BridgeProp` for T2."
                        )
                        sm_s2 = ExecutorStateMachine("S", t2_path, manifest_path, model_id, frozen_prefix_path=s_core_file, admissibility_path=adm_path, mock_generator=mock_generator, additional_context_prompt=s2_ctx)
                        r_s2 = sm_s2.run()
                        calib_report["lifted"]["s2_status"] = r_s2["final_status"]
                        s2_code = r_s2.get("verified_code") or ""

                        if r_s2["final_status"] == "COMPLETE":
                            # Rename S1 and L1 T1-specific specifications and proofs to _t1
                            s1_renamed = re.sub(r'\bBridgeProp\b', 'BridgeProp_T1', s1_code)
                            s1_renamed = re.sub(r'\bLiftedClaim\b', 'LiftedClaim_T1', s1_renamed)

                            l1_renamed = re.sub(r'\bBridgeProp\b', 'BridgeProp_T1', l1_code)
                            l1_renamed = re.sub(r'\bLiftedClaim\b', 'LiftedClaim_T1', l1_renamed)
                            l1_renamed = re.sub(r'\bpreservation_bridge\b', 'preservation_bridge_t1', l1_renamed)
                            l1_renamed = re.sub(r'\blifted_theorem\b', 'lifted_theorem_t1', l1_renamed)
                            
                            # Cumulative prefix for L2: S1 + L1 (renamed) + S2 specification for T2
                            l2_prefix = s1_renamed + "\n\n" + l1_renamed + "\n\n" + s2_code
                            with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False, dir=run_tmp_root) as f:
                                f.write(l2_prefix)
                                l2_prefix_file = f.name
                            try:
                                l2_ctx = (
                                    "REUSED REPRESENTATION INFRASTRUCTURE (from T1):\n"
                                    "The representation core and T1 lemmas are loaded in the environment:\n"
                                    f"```lean\n{l1_renamed}\n```\n"
                                    "Prove `preservation_bridge` and `lifted_theorem` for T2."
                                )
                                sm_l2 = ExecutorStateMachine("L", t2_path, manifest_path, model_id, frozen_prefix_path=l2_prefix_file, admissibility_path=adm_path, mock_generator=mock_generator, additional_context_prompt=l2_ctx)
                                r_l2 = sm_l2.run()
                                calib_report["lifted"]["l2_status"] = r_l2["final_status"]

                                if r_l2["final_status"] == "COMPLETE":
                                    l2_code = r_l2.get("verified_code") or ""
                                    cum_l_code = s1_code + "\n\n" + l1_code + "\n\n" + s2_code + "\n\n" + l2_code
                                    w_l_t1_t2 = count_tokens(cum_l_code)
                                    calib_report["lifted"]["w_l_t1_t2"] = w_l_t1_t2
                                    delta_l = max(0, w_l_t1_t2 - r_l1["verified_footprint_tokens"])
                                    calib_report["lifted"]["delta_l_2"] = delta_l
                                else:
                                    delta_l = None
                                    calib_report["lifted"]["w_l_t1_t2"] = None
                                    calib_report["lifted"]["delta_l_2"] = None
                            finally:
                                if os.path.exists(l2_prefix_file):
                                    os.remove(l2_prefix_file)
                        else:
                            delta_l = None
                            calib_report["lifted"]["l2_status"] = "SKIPPED_S2_FAILED"
                            calib_report["lifted"]["w_l_t1_t2"] = None
                            calib_report["lifted"]["delta_l_2"] = None
                    finally:
                        if os.path.exists(s_core_file):
                            os.remove(s_core_file)
                else:
                    delta_l = None
                    calib_report["lifted"]["s2_status"] = "SKIPPED_L1_FAILED"
                    calib_report["lifted"]["l2_status"] = "SKIPPED_L1_FAILED"
                    calib_report["lifted"]["w_l_t1_t2"] = None
                    calib_report["lifted"]["delta_l_2"] = None
            finally:
                if os.path.exists(s1_file):
                    os.remove(s1_file)
        else:
            delta_l = None
            calib_report["lifted"]["l1_status"] = "SKIPPED_S1_FAILED"
            calib_report["lifted"]["s2_status"] = "SKIPPED_S1_FAILED"
            calib_report["lifted"]["l2_status"] = "SKIPPED_S1_FAILED"
            calib_report["lifted"]["w_l_t1_t2"] = None
            calib_report["lifted"]["delta_l_2"] = None

        # H1 Dividend Evaluation: 2 * Delta_L^(2) <= Delta_D^(2) and W_L(T1+T2) < W_D(T1+T2)
        if delta_d is not None and delta_l is not None:
            marginal_satisfied = bool(2 * delta_l <= delta_d)
            cum_w_d = calib_report["direct"].get("w_d_t1_t2")
            cum_w_l = calib_report["lifted"].get("w_l_t1_t2")
            cum_satisfied = bool(cum_w_d is not None and cum_w_l is not None and cum_w_l < cum_w_d)
            ratio = round(delta_l / delta_d, 4) if delta_d > 0 else None
            calib_report["ratio_delta_l_over_delta_d"] = ratio
            calib_report["marginal_dividend_satisfied"] = marginal_satisfied
            calib_report["cumulative_amortization_satisfied"] = cum_satisfied
            calib_report["h1_dividend_satisfied"] = bool(marginal_satisfied and cum_satisfied)
        else:
            calib_report["ratio_delta_l_over_delta_d"] = None
            calib_report["marginal_dividend_satisfied"] = False
            calib_report["cumulative_amortization_satisfied"] = False
            calib_report["h1_dividend_satisfied"] = False

        receipt_file = os.path.join(TOOLS_DIR, f"execution_receipt_calibration_{family_name}_{model_id}.json")
        with open(receipt_file, "w", encoding="utf-8") as f:
            json.dump(calib_report, f, indent=2)
        legacy_receipt_file = os.path.join(TOOLS_DIR, f"execution_receipt_calibration_{family_name}.json")
        try:
            with open(legacy_receipt_file, "w", encoding="utf-8") as f:
                json.dump(calib_report, f, indent=2)
        except OSError:
            pass

        return calib_report
    finally:
        if own_tmp_ctx:
            own_tmp_ctx.cleanup()

def run_blind_case(
    case_id: str,
    target_path: str,
    model_id: str,
    admissibility_path: str | None = None,
    mock_generator=None,
    on_d_complete_callback=None,
    run_tmp_root: str | None = None
) -> dict:
    """
    Executes the blind transfer case evaluation driver (H2):
    Pipeline: Direct (D) -> Representation Search (S) -> Lifted Proof (L)
    
    Governance & Non-Persistence Rules:
    1. Zero Pre-Execution Residuals:
       - Purges stale single-role or blind receipts.
    2. D-Branch Non-Persistence:
       - Role D executes first on frozen target.
       - Proof code, token footprint, and transcripts are retained strictly in memory.
       - Single-role receipt is never written to disk during paired run.
    3. Inter-Branch Isolation Boundary:
       - Invokes on_d_complete_callback to assert zero D artifacts exist in repo or run_tmp_root.
    4. Representation Search (Role S) & Preregistered Classification:
       - Role S executes independently on target.
       - If S fails to find a valid representation stub, status is classified fail-closed as
         LIFT_NOT_FOUND (or INFRA_FAILURE if transport failure).
       - NO RESAMPLING is permitted.
       - Role L is skipped with status SKIPPED_LIFT_NOT_FOUND.
    5. Lifted Proof (Role L):
       - If S completes, S stub is staged temporarily in run_tmp_root for Role L only.
       - Role L authors preservation_bridge and lifted_theorem.
       - S stub file is removed immediately after L completes.
    6. Joint Atomic Receipt:
       - Atomically emits execution_receipt_blind_{case_id}.json after all roles terminate.
    """
    import tempfile
    
    own_tmp_ctx = None
    if not run_tmp_root:
        own_tmp_ctx = tempfile.TemporaryDirectory()
        run_tmp_root = own_tmp_ctx.name

    try:
        # Purge stale receipts
        stale_receipts = [
            os.path.join(TOOLS_DIR, "execution_receipt_d.json"),
            os.path.join(TOOLS_DIR, "execution_receipt_s.json"),
            os.path.join(TOOLS_DIR, "execution_receipt_l.json"),
            os.path.join(TOOLS_DIR, f"execution_receipt_blind_{case_id}.json"),
            os.path.join(TOOLS_DIR, f"execution_receipt_blind_{case_id}_{model_id}.json")
        ]
        for sr in stale_receipts:
            if os.path.exists(sr):
                try:
                    os.remove(sr)
                except OSError:
                    pass

        if not os.path.exists(target_path):
            raise FileNotFoundError(f"Blind target file '{target_path}' not found.")

        manifest_path = admissibility_path if (admissibility_path and os.path.exists(admissibility_path)) else os.path.join(ROOT_DIR, "admissibility", "default.json")

        blind_report = {
            "schema_version": "representation-lifting-execution-receipt/v1",
            "receipt_type": "blind_case_execution_receipt",
            "case_id": case_id,
            "target_path": os.path.abspath(target_path),
            "target_sha256": sha256_file(target_path),
            "model_id": model_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "direct": {},
            "representation_search": {},
            "lifted": {},
            "outcome": "PENDING"
        }

        # --- 1. DIRECT BRANCH (in-memory) ---
        sm_d = ExecutorStateMachine("D", target_path, manifest_path, model_id, admissibility_path=admissibility_path, mock_generator=mock_generator)
        r_d = sm_d.run()
        blind_report["direct"] = {
            "final_status": r_d["final_status"],
            "turns_consumed": r_d["turns_consumed"],
            "wallclock_seconds": r_d["wallclock_seconds"],
            "verified_footprint_tokens": r_d["verified_footprint_tokens"],
            "verified_code": r_d.get("verified_code")
        }

        # Inter-branch boundary hook
        if on_d_complete_callback:
            on_d_complete_callback(blind_report)

        # --- 2. REPRESENTATION SEARCH (Role S) ---
        sm_s = ExecutorStateMachine("S", target_path, manifest_path, model_id, admissibility_path=admissibility_path, mock_generator=mock_generator)
        r_s = sm_s.run()
        s_code = r_s.get("verified_code") or ""
        s_status = r_s["final_status"]
        if s_status != "COMPLETE" and s_status != "INFRA_FAILURE":
            s_status = "LIFT_NOT_FOUND"

        blind_report["representation_search"] = {
            "final_status": s_status,
            "raw_status": r_s["final_status"],
            "turns_consumed": r_s["turns_consumed"],
            "wallclock_seconds": r_s["wallclock_seconds"],
            "verified_code": s_code if s_status == "COMPLETE" else None
        }

        # --- 3. LIFTED PROOF (Role L) ---
        if s_status == "COMPLETE":
            with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False, dir=run_tmp_root) as f:
                f.write(s_code)
                s_prefix_file = f.name
            try:
                sm_l = ExecutorStateMachine("L", target_path, manifest_path, model_id, frozen_prefix_path=s_prefix_file, admissibility_path=admissibility_path, mock_generator=mock_generator)
                r_l = sm_l.run()
                blind_report["lifted"] = {
                    "final_status": r_l["final_status"],
                    "turns_consumed": r_l["turns_consumed"],
                    "wallclock_seconds": r_l["wallclock_seconds"],
                    "verified_footprint_tokens": r_l["verified_footprint_tokens"],
                    "verified_code": r_l.get("verified_code")
                }
            finally:
                if os.path.exists(s_prefix_file):
                    os.remove(s_prefix_file)
        else:
            blind_report["lifted"] = {
                "final_status": f"SKIPPED_{s_status}",
                "turns_consumed": 0,
                "wallclock_seconds": 0.0,
                "verified_footprint_tokens": None,
                "verified_code": None
            }

        # Overall Case Outcome Classification
        if r_d["final_status"] == "INFRA_FAILURE" or r_s["final_status"] == "INFRA_FAILURE" or blind_report["lifted"]["final_status"] == "INFRA_FAILURE":
            blind_report["outcome"] = "INFRA_FAILURE"
        elif s_status == "LIFT_NOT_FOUND":
            blind_report["outcome"] = "LIFT_NOT_FOUND"
        elif blind_report["lifted"]["final_status"] == "COMPLETE":
            blind_report["outcome"] = "LIFTED_PROVEN"
        else:
            blind_report["outcome"] = "LIFTED_FAILED"

        # Emit joint receipt atomically
        receipt_file = os.path.join(TOOLS_DIR, f"execution_receipt_blind_{case_id}_{model_id}.json")
        with open(receipt_file, "w", encoding="utf-8") as f:
            json.dump(blind_report, f, indent=2)
        legacy_receipt_file = os.path.join(TOOLS_DIR, f"execution_receipt_blind_{case_id}.json")
        try:
            with open(legacy_receipt_file, "w", encoding="utf-8") as f:
                json.dump(blind_report, f, indent=2)
        except OSError:
            pass

        return blind_report
    finally:
        if own_tmp_ctx:
            own_tmp_ctx.cleanup()

def run_control_case(
    model_id: str,
    target_path: str | None = None,
    stub_path: str | None = None,
    admissibility_path: str | None = None,
    mock_generator=None,
    on_d_complete_callback=None,
    run_tmp_root: str | None = None,
    receipt_out_path: str | None = None
) -> dict:
    """
    Executes the negative control arm evaluation driver (H0):
    Pipeline: Direct (D) -> Lifted Proof (L) [using pre-frozen Gnomon stub, Role S skipped]
    
    Governance & Non-Persistence Rules:
    1. Zero Pre-Execution Residuals:
       - Purges stale control or single-role receipts.
    2. D-Branch Non-Persistence:
       - Role D executes first on frozen target in memory only.
       - Proof code, token footprint, and transcripts are retained strictly in memory.
       - Single-role receipt is never written to disk during paired run.
    3. Inter-Branch Isolation Boundary:
       - Invokes on_d_complete_callback to assert zero D artifacts exist in repo or run_tmp_root.
    4. Lifted Proof (Role L):
       - Executes using the committed Gnomon stub (calibration/ControlGnomonStub.lean).
       - Zero search execution (Role S is not executed for control).
    5. Joint Atomic Receipt:
       - Emits execution_receipt_control.json atomically after both branches conclude.
    """
    import tempfile
    
    own_tmp_ctx = None
    if not run_tmp_root:
        own_tmp_ctx = tempfile.TemporaryDirectory()
        run_tmp_root = own_tmp_ctx.name

    if target_path is None:
        target_path = os.path.join(ROOT_DIR, "calibration", "control_sum_odd.lean")
    if stub_path is None:
        stub_path = os.path.join(ROOT_DIR, "calibration", "ControlGnomonStub.lean")

    try:
        # Purge stale receipts
        stale_receipts = [
            os.path.join(TOOLS_DIR, "execution_receipt_d.json"),
            os.path.join(TOOLS_DIR, "execution_receipt_l.json"),
            os.path.join(TOOLS_DIR, "execution_receipt_control.json"),
            os.path.join(TOOLS_DIR, f"execution_receipt_control_{model_id}.json")
        ]
        for sr in stale_receipts:
            if os.path.exists(sr):
                try:
                    os.remove(sr)
                except OSError:
                    pass

        if not os.path.exists(target_path):
            raise FileNotFoundError(f"Control target file '{target_path}' not found.")
        if not os.path.exists(stub_path):
            raise FileNotFoundError(f"Control stub file '{stub_path}' not found.")

        manifest_path = admissibility_path if (admissibility_path and os.path.exists(admissibility_path)) else os.path.join(ROOT_DIR, "admissibility", "default.json")

        control_report = {
            "schema_version": "representation-lifting-execution-receipt/v1",
            "receipt_type": "control_case_execution_receipt",
            "target_path": os.path.abspath(target_path),
            "target_sha256": sha256_file(target_path),
            "stub_path": os.path.abspath(stub_path),
            "stub_sha256": sha256_file(stub_path),
            "model_id": model_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "direct": {},
            "lifted": {}
        }

        # --- 1. DIRECT BRANCH (in-memory) ---
        sm_d = ExecutorStateMachine("D", target_path, manifest_path, model_id, admissibility_path=admissibility_path, mock_generator=mock_generator)
        r_d = sm_d.run()
        control_report["direct"] = {
            "final_status": r_d["final_status"],
            "turns_consumed": r_d["turns_consumed"],
            "wallclock_seconds": r_d["wallclock_seconds"],
            "verified_footprint_tokens": r_d["verified_footprint_tokens"],
            "verified_code": r_d.get("verified_code")
        }

        # Inter-branch boundary hook
        if on_d_complete_callback:
            on_d_complete_callback(control_report)

        # --- 2. LIFTED PROOF (Role L with pre-frozen stub) ---
        sm_l = ExecutorStateMachine("L", target_path, manifest_path, model_id, frozen_prefix_path=stub_path, admissibility_path=admissibility_path, mock_generator=mock_generator)
        r_l = sm_l.run()
        control_report["lifted"] = {
            "final_status": r_l["final_status"],
            "turns_consumed": r_l["turns_consumed"],
            "wallclock_seconds": r_l["wallclock_seconds"],
            "verified_footprint_tokens": r_l["verified_footprint_tokens"],
            "verified_code": r_l.get("verified_code")
        }

        # Emit joint receipt atomically
        receipt_file = receipt_out_path or os.path.join(TOOLS_DIR, f"execution_receipt_control_{model_id}.json")
        with open(receipt_file, "w", encoding="utf-8") as f:
            json.dump(control_report, f, indent=2)
        if receipt_out_path is None:
            legacy_file = os.path.join(TOOLS_DIR, "execution_receipt_control.json")
            try:
                with open(legacy_file, "w", encoding="utf-8") as f:
                    json.dump(control_report, f, indent=2)
            except OSError:
                pass

        return control_report
    finally:
        if own_tmp_ctx:
            own_tmp_ctx.cleanup()

def main():
    if len(sys.argv) < 2:
        print(f"Usage:\n  {sys.argv[0]} calibration <family_name> <model_id>\n  {sys.argv[0]} blind <case_id> <target_file> <model_id> [admissibility_json]\n  {sys.argv[0]} control <model_id> [target_file] [stub_file] [admissibility_json]\n  [DEV-ONLY] {sys.argv[0]} <role:S|D|L> <target_file> <manifest_file> <model_id> [frozen_prefix_file] [admissibility_json] [--save-receipt]", file=sys.stderr)
        sys.exit(1)

    if sys.argv[1].lower() == "calibration":
        if len(sys.argv) < 4:
            print(f"Usage: {sys.argv[0]} calibration <family_name> <model_id>", file=sys.stderr)
            sys.exit(1)
        family_name = sys.argv[2]
        model_id = sys.argv[3]
        report = run_calibration_family(family_name, model_id)
        print(json.dumps(report, indent=2))
        sys.exit(0 if report["h1_dividend_satisfied"] else 1)

    if sys.argv[1].lower() == "blind":
        if len(sys.argv) < 5:
            print(f"Usage: {sys.argv[0]} blind <case_id> <target_file> <model_id> [admissibility_json]", file=sys.stderr)
            sys.exit(1)
        case_id = sys.argv[2]
        target_path = sys.argv[3]
        model_id = sys.argv[4]
        adm_json = sys.argv[5] if len(sys.argv) > 5 else None
        report = run_blind_case(case_id, target_path, model_id, admissibility_path=adm_json)
        print(json.dumps(report, indent=2))
        sys.exit(0 if report["outcome"] in ["LIFTED_PROVEN", "COMPLETE"] else 1)

    if sys.argv[1].lower() == "control":
        if len(sys.argv) < 3:
            print(f"Usage: {sys.argv[0]} control <model_id> [target_file] [stub_file] [admissibility_json]", file=sys.stderr)
            sys.exit(1)
        model_id = sys.argv[2]
        target_path = sys.argv[3] if len(sys.argv) > 3 else None
        stub_path = sys.argv[4] if len(sys.argv) > 4 else None
        adm_json = sys.argv[5] if len(sys.argv) > 5 else None
        report = run_control_case(model_id, target_path=target_path, stub_path=stub_path, admissibility_path=adm_json)
        print(json.dumps(report, indent=2))
        sys.exit(0 if report["direct"]["final_status"] == "COMPLETE" else 1)

    print("[DEV-ONLY] Standalone role invocation is for development/debugging only. Production experiments run via run_calibration_family, run_blind_case, or run_control_case.", file=sys.stderr)

    role = sys.argv[1].upper()
    target_path = sys.argv[2]
    manifest_path = sys.argv[3]
    model_id = sys.argv[4]
    frozen_prefix = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] != "" and not sys.argv[5].startswith("--") else None
    admissibility_json = sys.argv[6] if len(sys.argv) > 6 and not sys.argv[6].startswith("--") else None
    
    save_receipt = None
    if "--save-receipt" in sys.argv:
        save_receipt = os.path.join(TOOLS_DIR, f"execution_receipt_{role.lower()}.json")

    state_machine = ExecutorStateMachine(role, target_path, manifest_path, model_id, frozen_prefix, admissibility_path=admissibility_json, save_receipt_path=save_receipt)
    receipt = state_machine.run()
    
    print(f"\nExecution Finished. Status: {receipt['final_status']}")
    print(f"Turns: {receipt['turns_consumed']}, Elapsed: {receipt['wallclock_seconds']}s")
    if receipt["verified_footprint_tokens"] is not None:
        print(f"Verified Footprint Tokens: {receipt['verified_footprint_tokens']}")
    
    sys.exit(0 if receipt["final_status"] == "COMPLETE" else 1)

if __name__ == "__main__":
    main()
