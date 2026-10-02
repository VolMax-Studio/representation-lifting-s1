#!/usr/bin/env python3
"""
tools/a1_surface_bridge.py

Amendment A1 surface bridge for representation-lifting-s1.

Intercepts the inference boundary of the frozen executor_harness.py,
translating API calls into subscription-surface relays while preserving
the EXACT interface contract of call_model_api_with_resilience():

    Input:  (model_id, messages, system_prompt, remaining_wallclock, config, transcript)
    Output: (response_text: str, stop_reason: str | None, is_infra_failure: bool)

The frozen harness (tools/executor_harness.py) remains the SOLE AUTHORITY over:
  - Protocol-defined system prompt and message construction
  - Response parsing and Lean verification invocation
  - Compiler feedback construction
  - State-machine advancement and turn counting
  - Receipt emission

This bridge handles ONLY:
  1. Receive exact (model_id, system_prompt, messages) from frozen harness
  2. Emit canonical request_N.json + SHA-256
  3. Emit surface_input_N.txt + SHA-256
  4. Relay to the pinned subscription surface (CLI or manual)
  5. Emit response_N.txt + SHA-256
  6. Return (response_text, stop_reason, is_infra_failure) to frozen harness

CRITICAL CONSTRAINTS:
  - Zero Lean verification
  - Zero compiler feedback construction
  - Zero state-machine logic
  - Zero prompt generation
  - Zero theorem reasoning

Part of representation-lifting-s1 Amendment A1.
"""

import sys
import os
import json
import hashlib
import subprocess
import time
import shutil
from datetime import datetime, timezone
from typing import Optional

REQUEST_SCHEMA_VERSION = "representation-lifting-a1-request/v1"


# ---------------------------------------------------------------------------
# A1 config loading
# ---------------------------------------------------------------------------

def _load_a1_config(a1_config_path: Optional[str] = None) -> dict:
    if a1_config_path is None:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        a1_config_path = os.path.join(
            root, "evidence", "amendment_a1", "a1_transport_config.json"
        )
    with open(a1_config_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# SHA-256 utilities
# ---------------------------------------------------------------------------

def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))

def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Canonical request envelope
# ---------------------------------------------------------------------------

def emit_canonical_request(
    artifact_dir: str,
    turn_number: int,
    model_id: str,
    system_prompt: str,
    messages: list,
) -> tuple:
    """Write requests/request_N.json. Returns (path, sha256)."""
    os.makedirs(os.path.join(artifact_dir, "requests"), exist_ok=True)
    path = os.path.join(artifact_dir, "requests", f"request_{turn_number}.json")
    envelope = {
        "schema_version": REQUEST_SCHEMA_VERSION,
        "turn_number": turn_number,
        "model_id": model_id,
        "system_prompt": system_prompt,
        "messages": messages,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    canonical_bytes = json.dumps(envelope, sort_keys=True, ensure_ascii=False).encode("utf-8")
    sha = _sha256_bytes(canonical_bytes)
    envelope["sha256"] = sha
    with open(path, "wb") as f:
        f.write(json.dumps(envelope, indent=2, ensure_ascii=False).encode("utf-8"))
    with open(path + ".sha256", "w") as f:
        f.write(sha + "\n")
    return path, sha


# ---------------------------------------------------------------------------
# Surface relay artifact (flattening)
# ---------------------------------------------------------------------------

def _flatten_for_no_system_role(system_prompt: str, messages: list, scheme: dict) -> str:
    """Deterministic flattening for surfaces without caller-controlled system messages."""
    sys_start = scheme.get("system_delimiter_start",
        "=== PROTOCOL SYSTEM INSTRUCTIONS (DO NOT MODIFY) ===")
    sys_end = scheme.get("system_delimiter_end",
        "=== END PROTOCOL SYSTEM INSTRUCTIONS ===")
    hist_start = scheme.get("history_delimiter_start", "=== CONVERSATION HISTORY ===")
    turn_fmt = scheme.get("history_turn_format", "[Turn {n} - {ROLE}]:")
    hist_end = scheme.get("history_delimiter_end", "=== END CONVERSATION HISTORY ===")
    current_delim = scheme.get("current_delimiter", "=== CURRENT REQUEST ===")

    parts = [sys_start, "", system_prompt, "", sys_end]
    history = messages[:-1]
    current_msg = messages[-1] if messages else None

    if history:
        parts += ["", hist_start, ""]
        turn_idx = 1
        for msg in history:
            role_label = "USER" if msg["role"] == "user" else "ASSISTANT"
            header = turn_fmt.format(n=turn_idx, ROLE=role_label)
            if msg["role"] == "assistant":
                turn_idx += 1
            parts += [header, msg["content"], ""]
        parts.append(hist_end)

    parts += ["", current_delim, ""]
    if current_msg is not None:
        parts.append(current_msg["content"])
    return "\n".join(parts)


def emit_surface_input(
    artifact_dir: str, turn_number: int, system_prompt: str,
    messages: list, surface_config: dict,
) -> tuple:
    """Produce surface_input_N.txt. Returns (path, sha256, system_role_handling)."""
    os.makedirs(os.path.join(artifact_dir, "requests"), exist_ok=True)
    path = os.path.join(artifact_dir, "requests", f"surface_input_{turn_number}.txt")
    system_role_handling = surface_config.get("system_role_handling", "NATIVE_SYSTEM_MESSAGE")

    if system_role_handling == "NATIVE_SYSTEM_MESSAGE":
        current_msg = messages[-1] if messages else {"content": ""}
        surface_text = current_msg["content"]
    else:
        scheme = surface_config.get("flattening_scheme", {})
        surface_text = _flatten_for_no_system_role(system_prompt, messages, scheme)

    data = surface_text.encode("utf-8")
    sha = _sha256_bytes(data)
    with open(path, "wb") as f:
        f.write(data)
    with open(path + ".sha256", "w") as f:
        f.write(sha + "\n")
    return path, sha, system_role_handling


# ---------------------------------------------------------------------------
# Response artifact
# ---------------------------------------------------------------------------

def emit_response(artifact_dir: str, turn_number: int, response_text: str) -> tuple:
    """Write responses/response_N.txt. Returns (path, sha256)."""
    os.makedirs(os.path.join(artifact_dir, "responses"), exist_ok=True)
    path = os.path.join(artifact_dir, "responses", f"response_{turn_number}.txt")
    data = response_text.encode("utf-8")
    sha = _sha256_bytes(data)
    with open(path, "wb") as f:
        f.write(data)
    with open(path + ".sha256", "w") as f:
        f.write(sha + "\n")
    return path, sha


# ---------------------------------------------------------------------------
# Transport failure classification
# ---------------------------------------------------------------------------

def is_pre_response_transport_failure(exc: Exception) -> bool:
    """
    Returns True ONLY for failures before any response message is produced:
    connection failure, pre-content timeout, surface crash, CLI not found.
    A delivered response (even empty text) is NOT a transport failure.
    """
    return isinstance(exc, (
        subprocess.TimeoutExpired,
        FileNotFoundError,
        ConnectionError,
        OSError,
        BrokenPipeError,
    ))


# ---------------------------------------------------------------------------
# Claude Code CLI relay
# ---------------------------------------------------------------------------

def _relay_claude_code_cli(
    surface_input_path: str,
    surface_config: dict,
    system_prompt: str,
    remaining_wallclock: float,
    transcript: list,
) -> tuple:
    """Invoke Claude Code CLI with pinned flags. Returns (response_text, stop_reason, is_infra_failure)."""
    pinned_model = surface_config.get("pinned_model_id", "claude-sonnet-4-6")
    effort = surface_config.get("inference_controls_pinned", {}).get("reasoning_effort", "high")
    if effort in ("NOT_EXPOSED", "N/A", None):
        effort = "high"

    with open(surface_input_path, "r", encoding="utf-8") as f:
        user_content = f.read()

    timeout = min(
        surface_config.get("request_timeout_seconds", 600),
        max(5.0, remaining_wallclock - 2.0),
    )
    claude_exe = surface_config.get("executable_path", "")
    if not claude_exe or not os.path.isfile(claude_exe):
        claude_exe = shutil.which("claude") or "claude"

    cmd = [
        claude_exe,
        "--model", pinned_model,
        "--effort", effort,
        "--safe-mode",
        "--tools", "",
        "--system-prompt", system_prompt,
        "--print",
        user_content,
    ]
    transcript.append({
        "event": "a1_bridge_cli_invocation",
        "model": pinned_model,
        "effort": effort,
        "timeout_seconds": round(timeout, 1),
    })
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0 and not result.stdout.strip():
            transcript.append({"event": "a1_bridge_cli_error",
                "returncode": result.returncode, "stderr": result.stderr[:500]})
            return "", None, True
        response_text = result.stdout
        transcript.append({"event": "a1_bridge_cli_success",
            "returncode": result.returncode, "response_length": len(response_text)})
        return response_text, "end_turn", False
    except subprocess.TimeoutExpired:
        transcript.append({"event": "a1_bridge_cli_timeout"})
        return "", None, True
    except (FileNotFoundError, OSError) as exc:
        transcript.append({"event": "a1_bridge_cli_not_found", "error": str(exc)})
        return "", None, True


# ---------------------------------------------------------------------------
# Manual ChatGPT web relay
# ---------------------------------------------------------------------------

def _relay_manual_chatgpt(
    surface_input_path: str,
    response_collect_path: str,
    remaining_wallclock: float,
    transcript: list,
) -> tuple:
    """
    Human-courier relay for ChatGPT web.
    Bridge pauses; operator copies surface_input_N.txt verbatim into ChatGPT,
    then copies the complete response verbatim into response_collect_path.
    Returns (response_text, stop_reason, is_infra_failure).
    """
    deadline = time.time() + max(30.0, remaining_wallclock - 5.0)
    poll_interval = 3.0
    transcript.append({
        "event": "a1_bridge_manual_wait_start",
        "surface_input": surface_input_path,
        "response_target": response_collect_path,
        "deadline_remaining_seconds": round(remaining_wallclock, 1),
    })
    print(
        f"\n[A1 BRIDGE — MANUAL RELAY]\n"
        f"Copy the exact contents of:\n  {surface_input_path}\n"
        f"into the pinned ChatGPT web surface (GPT-5.6 Sol, fresh chat).\n"
        f"After receiving the complete model response, copy it verbatim into:\n"
        f"  {response_collect_path}\n"
        f"Then press Enter here, or wait for timeout.\n",
        flush=True,
    )
    os.makedirs(os.path.dirname(response_collect_path), exist_ok=True)
    try:
        import select as _select
        while time.time() < deadline:
            if os.path.isfile(response_collect_path):
                break
            r, _, _ = _select.select([sys.stdin], [], [], poll_interval)
            if r:
                sys.stdin.readline()
                break
    except Exception:
        while time.time() < deadline:
            if os.path.isfile(response_collect_path):
                break
            time.sleep(poll_interval)

    if not os.path.isfile(response_collect_path):
        transcript.append({"event": "a1_bridge_manual_timeout"})
        return "", None, True

    with open(response_collect_path, "r", encoding="utf-8") as f:
        response_text = f.read()
    transcript.append({
        "event": "a1_bridge_manual_response_received",
        "response_length": len(response_text),
    })
    return response_text, "end_turn", False


# ---------------------------------------------------------------------------
# Main bridge entry point — drop-in for call_model_api_with_resilience()
# ---------------------------------------------------------------------------

def a1_call_surface(
    model_id: str,
    messages: list,
    system_prompt: str,
    remaining_wallclock: float,
    config: dict,
    transcript: list,
    *,
    a1_config=None,
    a1_config_path=None,
    artifact_dir=None,
    turn_number: int = 0,
) -> tuple:
    """
    Drop-in replacement for call_model_api_with_resilience().
    Extra keyword args are supplied by the activation shim (a1_activate.py).
    Returns (response_text, stop_reason, is_infra_failure).
    """
    if remaining_wallclock <= 1.0:
        transcript.append({"event": "a1_bridge_wallclock_expired_pre_request"})
        return "", "timeout_wallclock", False

    if a1_config is None:
        a1_config = _load_a1_config(a1_config_path)

    surfaces = a1_config.get("surfaces", {})
    surface_key = next(
        (k for k, sc in surfaces.items() if sc.get("pinned_model_id") == model_id),
        None,
    )
    if surface_key is None:
        transcript.append({"event": "a1_bridge_unknown_model", "model_id": model_id})
        return "", None, True
    surface_config = surfaces[surface_key]

    if artifact_dir is None:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        artifact_dir = os.path.join(root, "evidence", "amendment_a1", "run_artifacts")
    os.makedirs(artifact_dir, exist_ok=True)

    # 1. Emit canonical request envelope
    req_path, req_sha = emit_canonical_request(
        artifact_dir, turn_number, model_id, system_prompt, messages
    )
    transcript.append({"event": "a1_bridge_request_emitted",
        "path": req_path, "sha256": req_sha})

    # 2. Emit surface relay artifact
    si_path, si_sha, sys_role_handling = emit_surface_input(
        artifact_dir, turn_number, system_prompt, messages, surface_config
    )
    transcript.append({"event": "a1_bridge_surface_input_emitted",
        "path": si_path, "sha256": si_sha, "system_role_handling": sys_role_handling})

    # 3. Relay to surface
    surface_type = surface_config.get("surface_type", "claude-code-cli")
    if surface_type == "claude-code-cli":
        response_text, stop_reason, infra_fail = _relay_claude_code_cli(
            si_path, surface_config, system_prompt, remaining_wallclock, transcript
        )
    elif surface_type == "chatgpt-web":
        resp_collect_path = os.path.join(
            artifact_dir, "responses", f"response_{turn_number}.txt"
        )
        os.makedirs(os.path.dirname(resp_collect_path), exist_ok=True)
        response_text, stop_reason, infra_fail = _relay_manual_chatgpt(
            si_path, resp_collect_path, remaining_wallclock, transcript
        )
    else:
        transcript.append({"event": "a1_bridge_unknown_surface_type", "type": surface_type})
        return "", None, True

    if infra_fail:
        transcript.append({"event": "a1_bridge_infra_failure"})
        return "", None, True

    # 4. Emit response artifact — always, even if response_text is empty
    resp_path, resp_sha = emit_response(artifact_dir, turn_number, response_text)
    transcript.append({"event": "a1_bridge_response_emitted",
        "path": resp_path, "sha256": resp_sha, "response_length": len(response_text)})

    return response_text, stop_reason, False


# ---------------------------------------------------------------------------
# Gate 5 constants and probe runner
# ---------------------------------------------------------------------------

GATE5_SYSTEM_PROMPT = "Gate 5 smoke test. Follow the user instruction exactly."
GATE5_USER_CONTENT = (
    'Respond with exactly the following JSON and nothing else:\n'
    '{"status": "ok", "probe": "representation-lifting-s1-gate5"}'
)
GATE5_EXPECTED_RESPONSE = (
    '{"status": "ok", "probe": "representation-lifting-s1-gate5"}'
)


def run_gate5_probe(
    model_id: str,
    a1_config: dict,
    artifact_dir: str,
    config: Optional[dict] = None,
) -> dict:
    """
    Execute the Gate 5 neutral inference probe for a given model_id.
    Contains ZERO blind theorem content.
    Returns result dict with gate5_pass bool and evidence fields.
    """
    if config is None:
        config = {}
    transcript: list = []
    messages = [{"role": "user", "content": GATE5_USER_CONTENT}]

    response_text, stop_reason, infra_fail = a1_call_surface(
        model_id=model_id,
        messages=messages,
        system_prompt=GATE5_SYSTEM_PROMPT,
        remaining_wallclock=120.0,
        config=config,
        transcript=transcript,
        a1_config=a1_config,
        artifact_dir=artifact_dir,
        turn_number=0,
    )
    if infra_fail:
        return {"gate5_pass": False, "failure_reason": "INFRA_FAILURE", "transcript": transcript}

    # Exact-match check: strip whitespace and optional code fences
    stripped = response_text.strip()
    for fence in ["```json", "```"]:
        if stripped.startswith(fence):
            stripped = stripped[len(fence):]
    if stripped.endswith("```"):
        stripped = stripped[:-3]
    stripped = stripped.strip()

    exact_match = (stripped == GATE5_EXPECTED_RESPONSE)
    return {
        "gate5_pass": exact_match,
        "response_text": response_text,
        "response_stripped": stripped,
        "expected": GATE5_EXPECTED_RESPONSE,
        "exact_match": exact_match,
        "failure_reason": None if exact_match else "RESPONSE_NOT_EXACT_MATCH",
        "transcript": transcript,
    }


# ---------------------------------------------------------------------------
# CLI entry point (Gate 5 only — no blind content)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="A1 Surface Bridge — Gate 5 neutral probe (no blind content)"
    )
    parser.add_argument("--gate5", action="store_true", help="Run Gate 5 neutral probe")
    parser.add_argument("--model", default="claude-sonnet-4-6")
    parser.add_argument("--a1-config", default=None)
    parser.add_argument("--artifact-dir", default=None)
    args = parser.parse_args()

    if args.gate5:
        cfg = _load_a1_config(args.a1_config)
        art_dir = args.artifact_dir or os.path.join(
            os.path.dirname(__file__), "..", "evidence", "amendment_a1", "gate5"
        )
        result = run_gate5_probe(args.model, cfg, art_dir)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("gate5_pass") else 1)
    else:
        parser.print_help()
