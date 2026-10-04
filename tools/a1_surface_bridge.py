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
import tempfile
import re
from datetime import datetime, timezone
from typing import Optional

REQUEST_SCHEMA_VERSION = "representation-lifting-a1-request/v1"
ATTEMPT_SCHEMA_VERSION = "representation-lifting-a1-transport-attempt/v1"


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


def _flatten_history_for_native_system(messages: list, scheme: dict) -> str:
    """Preserve the frozen message history when the surface gets system_prompt natively
    but each bridge call is a fresh stateless CLI invocation.
    """
    if not messages:
        return ""
    if len(messages) == 1:
        return messages[0]["content"]

    hist_start = scheme.get("history_delimiter_start", "=== CONVERSATION HISTORY ===")
    turn_fmt = scheme.get("history_turn_format", "[Turn {n} - {ROLE}]:")
    hist_end = scheme.get("history_delimiter_end", "=== END CONVERSATION HISTORY ===")
    current_delim = scheme.get("current_delimiter", "=== CURRENT REQUEST ===")

    parts = [hist_start, ""]
    turn_idx = 1
    for msg in messages[:-1]:
        role_label = "USER" if msg["role"] == "user" else "ASSISTANT"
        parts += [turn_fmt.format(n=turn_idx, ROLE=role_label), msg["content"], ""]
        if msg["role"] == "assistant":
            turn_idx += 1
    parts += [hist_end, "", current_delim, "", messages[-1]["content"]]
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
        history_handling = surface_config.get("message_history_handling", "NATIVE_MULTI_TURN")
        if history_handling == "DEGRADED_HISTORY_FLATTENED_TO_USER_CONTENT":
            scheme = surface_config.get("flattening_scheme", {})
            surface_text = _flatten_history_for_native_system(messages, scheme)
        else:
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
# Transport metadata artifact (§A1.17 / Finding F6)
# ---------------------------------------------------------------------------

def emit_transport_metadata(
    artifact_dir: str, turn_number: int, metadata: dict
) -> tuple:
    """Write transport_metadata/transport_metadata_N.json and .sha256. Returns (path, sha256)."""
    meta_dir = os.path.join(artifact_dir, "transport_metadata")
    os.makedirs(meta_dir, exist_ok=True)
    path = os.path.join(meta_dir, f"transport_metadata_{turn_number}.json")
    envelope = {
        "schema_version": "representation-lifting-a1-transport-metadata/v1",
        "turn_number": turn_number,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        **metadata,
    }
    canonical_bytes = json.dumps(envelope, sort_keys=True, ensure_ascii=False).encode("utf-8")
    sha = _sha256_bytes(canonical_bytes)
    envelope["sha256"] = sha
    with open(path, "wb") as f:
        f.write(json.dumps(envelope, indent=2, ensure_ascii=False).encode("utf-8") + b"\n")
    with open(path + ".sha256", "w", encoding="utf-8") as f:
        f.write(f"{sha}  {os.path.basename(path)}\n")
    return path, sha


def _write_hash_addressed_bytes(path: str, data: bytes) -> tuple[str, str]:
    """Create an immutable evidence file and companion SHA-256 file."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    digest = _sha256_bytes(data)
    with open(path, "xb") as f:
        f.write(data)
    with open(path + ".sha256", "x", encoding="utf-8") as f:
        f.write(f"{digest}  {os.path.basename(path)}\n")
    return path, digest


def _redact_transport_secrets(text: str) -> tuple[str, bool]:
    """Redact credential-shaped material while otherwise preserving raw CLI streams."""
    patterns = [
        (re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s\"']+"), r"\1[REDACTED]"),
        (re.compile(r"\bsk-ant-[A-Za-z0-9_-]{12,}\b"), "[REDACTED_ANTHROPIC_TOKEN]"),
        (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "[REDACTED_API_TOKEN]"),
    ]
    redacted = text
    changed = False
    for pattern, replacement in patterns:
        redacted, count = pattern.subn(replacement, redacted)
        changed = changed or bool(count)
    return redacted, changed


def _safe_error_fields(event: Optional[dict]) -> dict:
    """Retain machine-readable error metadata without copying response/content bodies."""
    if not isinstance(event, dict):
        return {}
    permitted = (
        "type", "subtype", "error", "error_type", "code", "status",
        "status_code", "is_error", "isApiErrorMessage",
    )
    out = {}
    for key in permitted:
        value = event.get(key)
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            out[key] = value
        elif isinstance(value, dict):
            out[key] = {
                k: v for k, v in value.items()
                if k in ("type", "code", "status", "status_code")
                and isinstance(v, (str, int, float, bool))
            }
    return out


def _emit_attempt_raw(attempt_dir: str, stdout_text: str, stderr_text: str) -> dict:
    """Persist raw streams immediately, before parsing or semantic classification."""
    stdout_text, stdout_redacted = _redact_transport_secrets(stdout_text)
    stderr_text, stderr_redacted = _redact_transport_secrets(stderr_text)
    stdout_path, stdout_sha = _write_hash_addressed_bytes(
        os.path.join(attempt_dir, "raw_stdout.stream.jsonl"), stdout_text.encode("utf-8")
    )
    stderr_path, stderr_sha = _write_hash_addressed_bytes(
        os.path.join(attempt_dir, "raw_stderr.txt"), stderr_text.encode("utf-8")
    )
    return {
        "raw_stdout": {"path": os.path.basename(stdout_path), "sha256": stdout_sha},
        "raw_stderr": {"path": os.path.basename(stderr_path), "sha256": stderr_sha},
        "redactions_applied": bool(stdout_redacted or stderr_redacted),
    }


def _emit_attempt_manifest(
    attempt_dir: str,
    *,
    turn_number: int,
    attempt_number: int,
    raw_evidence: dict,
    returncode: Optional[int],
    parsed: dict,
    classification: str,
    response_delivered: bool,
) -> tuple[str, str]:
    """Bind already-persisted raw evidence to the final attempt classification."""
    manifest = {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "turn_number": turn_number,
        "attempt_number": attempt_number,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        **raw_evidence,
        "cli_return_code": returncode,
        **parsed,
        "response_delivered": bool(response_delivered),
        "final_bridge_classification": classification,
    }
    manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"
    return _write_hash_addressed_bytes(
        os.path.join(attempt_dir, "attempt_metadata.json"), manifest_bytes
    )


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


def _classify_timeout_partial_stdout(stdout_text: str) -> dict:
    """Parse only transport-envelope facts needed to make timeout retry decisions."""
    init_event = None
    result_event = None
    assistant_events = []
    stream_error_events = []
    non_json_seen = False

    for raw_line in stdout_text.splitlines():
        if not raw_line.strip():
            continue
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            non_json_seen = True
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            init_event = event
        elif event.get("type") == "assistant":
            assistant_events.append(event)
        elif event.get("type") == "result":
            result_event = event
        elif event.get("type") == "error":
            stream_error_events.append(event)

    synthetic_seen = any(
        (event.get("message", {}) or {}).get("model") == "<synthetic>"
        for event in assistant_events
    )
    genuine_assistant_events = [
        event for event in assistant_events
        if (event.get("message", {}) or {}).get("model") != "<synthetic>"
    ]
    delivered_parts = []
    for event in genuine_assistant_events:
        content = (event.get("message", {}) or {}).get("content")
        if isinstance(content, str):
            delivered_parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    delivered_parts.append(block.get("text", ""))
                elif block not in (None, ""):
                    delivered_parts.append(json.dumps(block, ensure_ascii=False, sort_keys=True))
        else:
            delivered_parts.append(json.dumps(content, ensure_ascii=False, sort_keys=True))

    is_api_error_message = any(
        event.get("isApiErrorMessage") is True
        or (event.get("message", {}) or {}).get("isApiErrorMessage") is True
        for event in assistant_events
    )
    assistant_error_marker = any(
        event.get("error") not in (None, False, "")
        or (event.get("message", {}) or {}).get("error") not in (None, False, "")
        for event in assistant_events
    ) or bool(stream_error_events)
    result_is_error = result_event.get("is_error") if isinstance(result_event, dict) else None
    result_error_marker = bool(
        isinstance(result_event, dict)
        and (result_event.get("is_error") is True
             or result_event.get("error") not in (None, False, ""))
    )
    assistant_model = next((
        (event.get("message", {}) or {}).get("model")
        for event in reversed(assistant_events)
        if (event.get("message", {}) or {}).get("model") is not None
    ), None)
    objective_error_evidence = bool(
        is_api_error_message or assistant_error_marker or result_error_marker
    )
    successful_result_delivered = bool(
        isinstance(result_event, dict)
        and result_event.get("is_error") is not True
        and "result" in result_event
        and not synthetic_seen
    )
    genuine_content_delivered = bool(
        genuine_assistant_events or successful_result_delivered
    )
    response_text = (
        result_event.get("result", "")
        if successful_result_delivered else "".join(delivered_parts)
    )
    return {
        "response_text": response_text,
        "genuine_content_delivered": genuine_content_delivered,
        "synthetic_seen": synthetic_seen,
        "objective_error_evidence": objective_error_evidence,
        "non_json_seen": non_json_seen,
        "metadata": {
            "model_returned": init_event.get("model") if isinstance(init_event, dict) else None,
            "assistant_model": assistant_model,
            "tools": init_event.get("tools", []) if isinstance(init_event, dict) else [],
            "mcp_servers": init_event.get("mcp_servers", []) if isinstance(init_event, dict) else [],
            "permission_mode": init_event.get("permissionMode") if isinstance(init_event, dict) else None,
        },
        "parsed": {
            "init_model": init_event.get("model") if isinstance(init_event, dict) else None,
            "assistant_model": assistant_model,
            "is_api_error_message": is_api_error_message,
            "result_is_error": result_is_error,
            "result_subtype": result_event.get("subtype") if isinstance(result_event, dict) else None,
            "assistant_error_evidence": [
                _safe_error_fields(event) for event in assistant_events
                if _safe_error_fields(event)
            ],
            "stream_error_evidence": [
                _safe_error_fields(event) for event in stream_error_events
                if _safe_error_fields(event)
            ],
            "result_error_evidence": _safe_error_fields(result_event),
            "non_json_output_seen": non_json_seen,
            "synthetic_assistant_seen": synthetic_seen,
            "genuine_assistant_event_seen": bool(genuine_assistant_events),
            "actual_model_response_content_delivered": genuine_content_delivered,
            "error_evidence": {"exception_type": "TimeoutExpired"},
        },
    }


# ---------------------------------------------------------------------------
# Claude Code CLI relay
# ---------------------------------------------------------------------------

def _relay_claude_code_cli(
    surface_input_path: str,
    surface_config: dict,
    system_prompt: str,
    remaining_wallclock: float,
    transcript: list,
    attempt_dir: Optional[str] = None,
    turn_number: int = 0,
    attempt_number: int = 1,
) -> tuple:
    """Invoke Claude Code, preserve raw attempt evidence, then classify the stream."""
    pinned_model = surface_config.get("pinned_model_id", "claude-sonnet-4-6")
    allowed_labels = set(surface_config.get("allowed_model_labels", [pinned_model]))
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
        "--output-format", "stream-json",
        "--verbose",
        "--no-session-persistence",
        "--max-turns", "1",
        user_content,
    ]
    transcript.append({
        "event": "a1_bridge_cli_invocation",
        "model_requested": pinned_model,
        "effort": effort,
        "timeout_seconds": round(timeout, 1),
    })
    raw_evidence = None

    def finish(
        classification: str,
        response_delivered: bool,
        metadata: dict,
        result_tuple: tuple,
        *,
        stdout_text: str,
        stderr_text: str,
        returncode: Optional[int],
        parsed: dict,
    ) -> tuple:
        nonlocal raw_evidence
        metadata = {
            **metadata,
            "response_delivered": bool(response_delivered),
            "final_bridge_classification": classification,
        }
        if attempt_dir is not None:
            if raw_evidence is None:
                raw_evidence = _emit_attempt_raw(attempt_dir, stdout_text, stderr_text)
            manifest_path, manifest_sha = _emit_attempt_manifest(
                attempt_dir,
                turn_number=turn_number,
                attempt_number=attempt_number,
                raw_evidence=raw_evidence,
                returncode=returncode,
                parsed=parsed,
                classification=classification,
                response_delivered=response_delivered,
            )
            transcript.append({
                "event": "a1_bridge_attempt_evidence",
                "turn_number": turn_number,
                "attempt_number": attempt_number,
                "manifest_path": manifest_path,
                "manifest_sha256": manifest_sha,
                "classification": classification,
                "response_delivered": bool(response_delivered),
            })
        transcript.append({"event": "a1_bridge_transport_metadata", "metadata": metadata})
        return result_tuple

    try:
        with tempfile.TemporaryDirectory(prefix="representation_lifting_a1_") as clean_cwd:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, cwd=clean_cwd
            )
        stdout_text = result.stdout or ""
        stderr_text = result.stderr or ""
        if attempt_dir is not None:
            raw_evidence = _emit_attempt_raw(attempt_dir, stdout_text, stderr_text)
        if result.returncode != 0 and not result.stdout.strip():
            transcript.append({"event": "a1_bridge_cli_error",
                "returncode": result.returncode, "stderr": result.stderr[:500]})
            return finish(
                "PRE_RESPONSE_TRANSPORT_FAILURE", False,
                {"model_returned": None, "assistant_model": None, "tools": [],
                 "mcp_servers": [], "permission_mode": None, "stop_reason": "CLI_ERROR",
                 "is_infra_failure": True},
                ("", None, True), stdout_text=stdout_text, stderr_text=stderr_text,
                returncode=result.returncode,
                parsed={"is_api_error_message": False, "result_is_error": None,
                        "error_evidence": {"cli_nonzero_return": True}},
            )

        init_event = None
        result_event = None
        assistant_stop_reason = None
        assistant_model = None
        assistant_events = []
        stream_error_events = []
        non_json_seen = False
        for raw_line in result.stdout.splitlines():
            if not raw_line.strip():
                continue
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                transcript.append({"event": "a1_bridge_cli_non_json_output", "text": raw_line[:500]})
                non_json_seen = True
                continue
            if event.get("type") == "system" and event.get("subtype") == "init":
                init_event = event
            elif event.get("type") == "assistant":
                assistant_events.append(event)
                msg = event.get("message", {}) or {}
                assistant_stop_reason = msg.get("stop_reason") or assistant_stop_reason
                assistant_model = msg.get("model") or assistant_model
            elif event.get("type") == "result":
                result_event = event
            elif event.get("type") == "error":
                stream_error_events.append(event)

        synthetic_seen = any(
            (event.get("message", {}) or {}).get("model") == "<synthetic>"
            for event in assistant_events
        )
        is_api_error_message = any(
            event.get("isApiErrorMessage") is True
            or (event.get("message", {}) or {}).get("isApiErrorMessage") is True
            for event in assistant_events
        )
        assistant_error_marker = any(
            event.get("error") not in (None, False, "")
            or (event.get("message", {}) or {}).get("error") not in (None, False, "")
            for event in assistant_events
        ) or bool(stream_error_events)
        result_is_error = result_event.get("is_error") if isinstance(result_event, dict) else None
        result_error_marker = bool(
            isinstance(result_event, dict)
            and (result_event.get("is_error") is True
                 or result_event.get("error") not in (None, False, ""))
        )
        ordinary_assistant_content_delivered = any(
            (event.get("message", {}) or {}).get("model") != "<synthetic>"
            and (event.get("message", {}) or {}).get("content") not in (None, "", [])
            for event in assistant_events
        )
        delivered_assistant_text_parts = []
        for event in assistant_events:
            msg = event.get("message", {}) or {}
            if msg.get("model") == "<synthetic>":
                continue
            content = msg.get("content")
            if isinstance(content, str):
                delivered_assistant_text_parts.append(content)
            elif isinstance(content, list):
                delivered_assistant_text_parts.extend(
                    block.get("text", "") for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
        delivered_assistant_text = "".join(delivered_assistant_text_parts)
        successful_result_delivered = bool(
            isinstance(result_event, dict)
            and result_event.get("is_error") is not True
            and "result" in result_event
        )
        delivered_response_text = (
            result_event.get("result", "") if successful_result_delivered
            else delivered_assistant_text
        )
        any_model_response_delivered = bool(
            ordinary_assistant_content_delivered or successful_result_delivered
        )
        objective_error_evidence = bool(
            is_api_error_message or assistant_error_marker or result_error_marker
        )
        parsed = {
            "init_model": init_event.get("model") if isinstance(init_event, dict) else None,
            "assistant_model": assistant_model,
            "is_api_error_message": is_api_error_message,
            "result_is_error": result_is_error,
            "result_subtype": result_event.get("subtype") if isinstance(result_event, dict) else None,
            "assistant_error_evidence": [
                _safe_error_fields(event) for event in assistant_events
                if _safe_error_fields(event)
            ],
            "stream_error_evidence": [
                _safe_error_fields(event) for event in stream_error_events
                if _safe_error_fields(event)
            ],
            "result_error_evidence": _safe_error_fields(result_event),
            "non_json_output_seen": non_json_seen,
            "synthetic_assistant_seen": synthetic_seen,
            "actual_model_response_content_delivered": ordinary_assistant_content_delivered,
        }

        returned_model = init_event.get("model") if isinstance(init_event, dict) else None
        tools = init_event.get("tools", []) if isinstance(init_event, dict) else []
        mcp_servers = init_event.get("mcp_servers", []) if isinstance(init_event, dict) else []
        permission_mode = init_event.get("permissionMode") if isinstance(init_event, dict) else None
        base_metadata = {
            "model_returned": returned_model,
            "assistant_model": assistant_model,
            "tools": tools,
            "mcp_servers": mcp_servers,
            "permission_mode": permission_mode,
        }

        # Error semantics are resolved before ordinary assistant-model identity checks.
        if objective_error_evidence and not any_model_response_delivered:
            transcript.append({
                "event": "a1_bridge_pre_response_error_envelope",
                "synthetic_assistant_seen": synthetic_seen,
                "is_api_error_message": is_api_error_message,
                "result_is_error": result_is_error,
            })
            return finish(
                "PRE_RESPONSE_TRANSPORT_FAILURE", False,
                {**base_metadata, "stop_reason": "PRE_RESPONSE_TRANSPORT_FAILURE",
                 "is_infra_failure": True},
                ("", None, True), stdout_text=stdout_text, stderr_text=stderr_text,
                returncode=result.returncode, parsed=parsed,
            )

        if objective_error_evidence and any_model_response_delivered:
            transcript.append({
                "event": "a1_bridge_error_after_response_delivery",
                "is_api_error_message": is_api_error_message,
                "result_is_error": result_is_error,
            })
            return finish(
                "DELIVERED_RESPONSE_PROTOCOL_FAILURE", True,
                {**base_metadata, "stop_reason": "SURFACE_PROTOCOL_FAIL",
                 "is_infra_failure": True},
                (delivered_response_text, "SURFACE_PROTOCOL_FAIL", True),
                stdout_text=stdout_text, stderr_text=stderr_text,
                returncode=result.returncode, parsed=parsed,
            )

        if synthetic_seen and not objective_error_evidence:
            transcript.append({"event": "a1_bridge_unproven_synthetic_assistant"})
            return finish(
                "SYNTHETIC_WITHOUT_ERROR_EVIDENCE", False,
                {**base_metadata, "stop_reason": "SYNTHETIC_WITHOUT_ERROR_EVIDENCE",
                 "is_infra_failure": True},
                ("", "SYNTHETIC_WITHOUT_ERROR_EVIDENCE", True),
                stdout_text=stdout_text, stderr_text=stderr_text,
                returncode=result.returncode, parsed=parsed,
            )

        if init_event is None:
            transcript.append({"event": "a1_bridge_cli_missing_init_event"})
            return finish(
                "SURFACE_PROTOCOL_FAIL", False,
                {**base_metadata, "stop_reason": "SURFACE_PROTOCOL_FAIL", "is_infra_failure": True},
                ("", "SURFACE_PROTOCOL_FAIL", True), stdout_text=stdout_text,
                stderr_text=stderr_text, returncode=result.returncode, parsed=parsed,
            )
        transcript.append({
            "event": "a1_bridge_cli_init",
            "model_returned": returned_model,
            "tools": tools,
            "mcp_servers": mcp_servers,
            "permission_mode": init_event.get("permissionMode"),
            "cwd": init_event.get("cwd"),
        })
        if returned_model not in allowed_labels:
            transcript.append({
                "event": "a1_bridge_model_id_mismatch",
                "expected_allowed": sorted(allowed_labels),
                "returned": returned_model,
            })
            return finish(
                "MODEL_IDENTITY_FAIL", any_model_response_delivered,
                {**base_metadata, "stop_reason": "MODEL_IDENTITY_FAIL", "is_infra_failure": True},
                (delivered_response_text, "MODEL_IDENTITY_FAIL", True), stdout_text=stdout_text,
                stderr_text=stderr_text, returncode=result.returncode, parsed=parsed,
            )
        if assistant_model is not None and assistant_model not in allowed_labels:
            transcript.append({
                "event": "a1_bridge_assistant_model_id_mismatch",
                "expected_allowed": sorted(allowed_labels),
                "returned": assistant_model,
            })
            return finish(
                "MODEL_IDENTITY_FAIL", any_model_response_delivered,
                {**base_metadata, "stop_reason": "MODEL_IDENTITY_FAIL", "is_infra_failure": True},
                (delivered_response_text, "MODEL_IDENTITY_FAIL", True), stdout_text=stdout_text,
                stderr_text=stderr_text, returncode=result.returncode, parsed=parsed,
            )
        if tools:
            transcript.append({"event": "a1_bridge_unexpected_tools_exposed", "tools": tools})
            return finish(
                "UNAUTHORIZED_TOOL_EXPOSURE", any_model_response_delivered,
                {**base_metadata, "stop_reason": "UNAUTHORIZED_TOOL_EXPOSURE", "is_infra_failure": True},
                (delivered_response_text, "UNAUTHORIZED_TOOL_EXPOSURE", True), stdout_text=stdout_text,
                stderr_text=stderr_text, returncode=result.returncode, parsed=parsed,
            )
        if any(s.get("status") not in (None, "disabled") for s in mcp_servers):
            transcript.append({"event": "a1_bridge_unexpected_mcp_exposure", "mcp_servers": mcp_servers})
            return finish(
                "UNAUTHORIZED_TOOL_EXPOSURE", any_model_response_delivered,
                {**base_metadata, "stop_reason": "UNAUTHORIZED_TOOL_EXPOSURE", "is_infra_failure": True},
                (delivered_response_text, "UNAUTHORIZED_TOOL_EXPOSURE", True), stdout_text=stdout_text,
                stderr_text=stderr_text, returncode=result.returncode, parsed=parsed,
            )
        if result_event is None or result_event.get("is_error"):
            transcript.append({"event": "a1_bridge_cli_missing_or_error_result", "result": result_event})
            return finish(
                "SURFACE_PROTOCOL_FAIL", any_model_response_delivered,
                {**base_metadata, "stop_reason": "SURFACE_PROTOCOL_FAIL", "is_infra_failure": True},
                (delivered_response_text, "SURFACE_PROTOCOL_FAIL", True), stdout_text=stdout_text,
                stderr_text=stderr_text, returncode=result.returncode, parsed=parsed,
            )

        response_text = result_event.get("result", "")
        stop_reason = assistant_stop_reason or "end_turn"
        transcript.append({
            "event": "a1_bridge_cli_success",
            "returncode": result.returncode,
            "response_length": len(response_text),
            "model_returned": returned_model,
            "assistant_model": assistant_model,
            "stop_reason": stop_reason,
        })
        return finish(
            "DELIVERED_RESPONSE", True,
            {**base_metadata, "stop_reason": stop_reason, "is_infra_failure": False},
            (response_text, stop_reason, False), stdout_text=stdout_text,
            stderr_text=stderr_text, returncode=result.returncode, parsed=parsed,
        )
    except subprocess.TimeoutExpired as exc:
        transcript.append({"event": "a1_bridge_cli_timeout"})
        stdout_text = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr_text = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        if attempt_dir is not None:
            raw_evidence = _emit_attempt_raw(attempt_dir, stdout_text, stderr_text)
        partial = _classify_timeout_partial_stdout(stdout_text)
        base_metadata = partial["metadata"]
        if partial["genuine_content_delivered"]:
            transcript.append({"event": "a1_bridge_timeout_after_response_delivery"})
            return finish(
                "DELIVERED_RESPONSE_PROTOCOL_FAILURE", True,
                {**base_metadata, "stop_reason": "TIMEOUT_AFTER_RESPONSE_DELIVERY",
                 "is_infra_failure": True},
                (partial["response_text"], "TIMEOUT_AFTER_RESPONSE_DELIVERY", True),
                stdout_text=stdout_text, stderr_text=stderr_text, returncode=None,
                parsed=partial["parsed"],
            )
        if partial["synthetic_seen"] and not partial["objective_error_evidence"]:
            transcript.append({"event": "a1_bridge_timeout_unproven_synthetic_assistant"})
            return finish(
                "SYNTHETIC_WITHOUT_ERROR_EVIDENCE", False,
                {**base_metadata, "stop_reason": "SYNTHETIC_WITHOUT_ERROR_EVIDENCE",
                 "is_infra_failure": True},
                ("", "SYNTHETIC_WITHOUT_ERROR_EVIDENCE", True),
                stdout_text=stdout_text, stderr_text=stderr_text, returncode=None,
                parsed=partial["parsed"],
            )
        if partial["non_json_seen"]:
            transcript.append({"event": "a1_bridge_timeout_unclassifiable_partial_output"})
            return finish(
                "TIMEOUT_UNCLASSIFIABLE_PARTIAL_OUTPUT", False,
                {**base_metadata, "stop_reason": "TIMEOUT_UNCLASSIFIABLE_PARTIAL_OUTPUT",
                 "is_infra_failure": True},
                ("", "TIMEOUT_UNCLASSIFIABLE_PARTIAL_OUTPUT", True),
                stdout_text=stdout_text, stderr_text=stderr_text, returncode=None,
                parsed=partial["parsed"],
            )
        return finish(
            "PRE_RESPONSE_TRANSPORT_FAILURE", False,
            {**base_metadata, "stop_reason": "TIMEOUT", "is_infra_failure": True},
            ("", None, True), stdout_text=stdout_text, stderr_text=stderr_text,
            returncode=None,
            parsed=partial["parsed"],
        )
    except (FileNotFoundError, OSError) as exc:
        transcript.append({"event": "a1_bridge_cli_not_found", "error": str(exc)})
        if attempt_dir is not None:
            raw_evidence = _emit_attempt_raw(attempt_dir, "", str(exc))
        return finish(
            "PRE_RESPONSE_TRANSPORT_FAILURE", False,
            {"model_returned": None, "assistant_model": None, "tools": [], "mcp_servers": [],
             "permission_mode": None, "stop_reason": "CLI_NOT_FOUND", "is_infra_failure": True},
            ("", None, True), stdout_text="", stderr_text=str(exc), returncode=None,
            parsed={"is_api_error_message": False, "result_is_error": None,
                    "error_evidence": {"exception_type": type(exc).__name__}},
        )


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
        transcript.append({
            "event": "a1_bridge_transport_metadata",
            "metadata": {
                "model_returned": None,
                "assistant_model": None,
                "tools": [],
                "mcp_servers": [],
                "permission_mode": "manual",
                "stop_reason": "TIMEOUT",
                "is_infra_failure": True,
            },
        })
        return "", None, True

    with open(response_collect_path, "r", encoding="utf-8") as f:
        response_text = f.read()
    transcript.append({
        "event": "a1_bridge_manual_response_received",
        "response_length": len(response_text),
    })
    transcript.append({
        "event": "a1_bridge_transport_metadata",
        "metadata": {
            "model_returned": "gpt-5.6-sol",
            "assistant_model": "gpt-5.6-sol",
            "tools": [],
            "mcp_servers": [],
            "permission_mode": "manual",
            "stop_reason": "end_turn",
            "is_infra_failure": False,
        },
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
    execution_status = surface_config.get("execution_status")
    if isinstance(execution_status, str) and execution_status.startswith("NOT_EVALUABLE_INFRA"):
        transcript.append({
            "event": "a1_bridge_surface_disabled",
            "surface_key": surface_key,
            "status": execution_status,
        })
        return "", "SURFACE_DISABLED", True

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

    # 3. Relay to surface, preserving the frozen transport retry budget.
    surface_type = surface_config.get("surface_type", "claude-code-cli")
    policy = config.get("transport_policy", {}) if isinstance(config, dict) else {}
    max_attempts = int(policy.get("max_attempts_per_turn", 1))
    backoffs = list(policy.get("backoff_seconds", []))
    call_start = time.monotonic()
    response_text, stop_reason, infra_fail = "", None, True
    attempts_used = 0

    for attempt in range(1, max_attempts + 1):
        attempts_used = attempt
        elapsed = time.monotonic() - call_start
        effective_remaining = remaining_wallclock - elapsed
        if effective_remaining <= 1.0:
            transcript.append({"event": "a1_bridge_wallclock_expired_during_retry", "attempt": attempt})
            meta_dict = {
                "model_returned": None,
                "assistant_model": None,
                "tools": [],
                "mcp_servers": [],
                "permission_mode": None,
                "stop_reason": "timeout_wallclock",
                "is_infra_failure": True,
            }
            if artifact_dir:
                emit_transport_metadata(artifact_dir, turn_number, meta_dict)
            return "", "timeout_wallclock", False

        transcript.append({"event": "a1_bridge_transport_attempt", "attempt": attempt})
        if surface_type == "claude-code-cli":
            attempt_dir = os.path.join(
                artifact_dir, "transport_attempts", f"turn_{turn_number}", f"attempt_{attempt}"
            )
            response_text, stop_reason, infra_fail = _relay_claude_code_cli(
                si_path, surface_config, system_prompt, effective_remaining, transcript,
                attempt_dir=attempt_dir, turn_number=turn_number, attempt_number=attempt,
            )
        elif surface_type == "chatgpt-web":
            resp_collect_path = os.path.join(
                artifact_dir, "responses", f"response_{turn_number}.txt"
            )
            os.makedirs(os.path.dirname(resp_collect_path), exist_ok=True)
            response_text, stop_reason, infra_fail = _relay_manual_chatgpt(
                si_path, resp_collect_path, effective_remaining, transcript
            )
        else:
            transcript.append({"event": "a1_bridge_unknown_surface_type", "type": surface_type})
            return "", None, True

        if not infra_fail:
            break
        # Non-empty stop_reason marks a delivered/protocol failure and is never retried.
        # Only pre-response transport failures return infra_fail=True with stop_reason=None.
        if stop_reason is not None:
            transcript.append({"event": "a1_bridge_nonretryable_infra", "attempt": attempt, "reason": stop_reason})
            break
        if attempt < max_attempts:
            wait_time = backoffs[attempt - 1] if attempt - 1 < len(backoffs) else 0
            transcript.append({"event": "a1_bridge_transport_retry", "attempt": attempt, "backoff_seconds": wait_time})
            if wait_time > 0:
                time.sleep(wait_time)

    # 4. Resolve and emit transport metadata artifact (§A1.17 / Finding F6)
    meta_dict = None
    for ev in reversed(transcript):
        if ev.get("event") == "a1_bridge_transport_metadata":
            meta_dict = ev.get("metadata")
            break
    if meta_dict is None:
        meta_dict = {
            "model_returned": surface_config.get("pinned_model_id") if not infra_fail else None,
            "assistant_model": surface_config.get("pinned_model_id") if not infra_fail else None,
            "tools": [],
            "mcp_servers": [],
            "permission_mode": "default",
            "stop_reason": stop_reason or ("end_turn" if not infra_fail else "INFRA_FAILURE"),
            "is_infra_failure": bool(infra_fail),
        }

    attempt_refs = []
    for ev in transcript:
        if (ev.get("event") == "a1_bridge_attempt_evidence"
                and ev.get("turn_number") == turn_number):
            attempt_refs.append({
                "attempt_number": ev.get("attempt_number"),
                "manifest_path": ev.get("manifest_path"),
                "manifest_sha256": ev.get("manifest_sha256"),
                "classification": ev.get("classification"),
                "response_delivered": ev.get("response_delivered"),
            })
    meta_dict["transport_attempts"] = sorted(
        attempt_refs, key=lambda item: item.get("attempt_number") or 0
    )
    meta_dict["attempts_used"] = attempts_used
    meta_dict["frozen_max_attempts"] = max_attempts
    meta_dict["retry_exhausted"] = bool(
        infra_fail and stop_reason is None and attempts_used >= max_attempts
    )

    meta_path, meta_sha = emit_transport_metadata(artifact_dir, turn_number, meta_dict)
    transcript.append({
        "event": "a1_bridge_transport_metadata_emitted",
        "path": meta_path,
        "sha256": meta_sha,
    })

    if infra_fail:
        if meta_dict.get("response_delivered") is True:
            resp_path, resp_sha = emit_response(artifact_dir, turn_number, response_text)
            transcript.append({
                "event": "a1_bridge_invalid_response_preserved",
                "path": resp_path,
                "sha256": resp_sha,
                "response_length": len(response_text),
            })
        transcript.append({"event": "a1_bridge_infra_failure", "attempts": max_attempts})
        return "", stop_reason, True

    # 5. Emit response artifact — always, even if response_text is empty
    resp_path, resp_sha = emit_response(artifact_dir, turn_number, response_text)
    transcript.append({"event": "a1_bridge_response_emitted",
        "path": resp_path, "sha256": resp_sha, "response_length": len(response_text)})

    return response_text, stop_reason, False


def _validate_embedded_json_hash(path: str) -> tuple[bool, Optional[dict]]:
    """Validate the bridge JSON envelope convention without returning payload content."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        embedded = data.pop("sha256", None)
        actual = _sha256_bytes(
            json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
        )
        with open(path + ".sha256", "r", encoding="utf-8") as f:
            sidecar = f.read().strip().split()[0]
        return embedded == actual == sidecar, data
    except (OSError, ValueError, IndexError, json.JSONDecodeError):
        return False, None


def _validate_raw_hash(path: str, expected: Optional[str] = None) -> bool:
    try:
        actual = _sha256_file(path)
        with open(path + ".sha256", "r", encoding="utf-8") as f:
            sidecar = f.read().strip().split()[0]
        return actual == sidecar and (expected is None or actual == expected)
    except (OSError, IndexError):
        return False


def validate_turn_transport_custody(
    branch_artifact_dir: str, turn_number: int
) -> dict:
    """Validate r9 turn evidence without interpreting scientific response content."""
    failures = []
    req = os.path.join(branch_artifact_dir, "requests", f"request_{turn_number}.json")
    surface = os.path.join(branch_artifact_dir, "requests", f"surface_input_{turn_number}.txt")
    meta = os.path.join(
        branch_artifact_dir, "transport_metadata", f"transport_metadata_{turn_number}.json"
    )
    response = os.path.join(branch_artifact_dir, "responses", f"response_{turn_number}.txt")

    request_ok, _ = _validate_embedded_json_hash(req)
    metadata_ok, metadata = _validate_embedded_json_hash(meta)
    if not request_ok:
        failures.append("REQUEST_HASH_INVALID_OR_MISSING")
    if not _validate_raw_hash(surface):
        failures.append("SURFACE_INPUT_HASH_INVALID_OR_MISSING")
    if not metadata_ok or metadata is None:
        failures.append("TRANSPORT_METADATA_HASH_INVALID_OR_MISSING")
        return {"custody_pass": False, "failure_reasons": failures}

    refs = metadata.get("transport_attempts")
    if not isinstance(refs, list) or not refs:
        failures.append("ATTEMPT_EVIDENCE_MISSING")
        refs = []
    attempt_numbers = [ref.get("attempt_number") for ref in refs if isinstance(ref, dict)]
    if attempt_numbers != list(range(1, len(refs) + 1)):
        failures.append("ATTEMPT_SEQUENCE_INVALID")

    branch_root = os.path.realpath(branch_artifact_dir)
    manifests = []
    for ref in refs:
        if not isinstance(ref, dict):
            failures.append("ATTEMPT_REFERENCE_INVALID")
            continue
        manifest_path = ref.get("manifest_path")
        if not isinstance(manifest_path, str):
            failures.append("ATTEMPT_MANIFEST_PATH_MISSING")
            continue
        real_manifest = os.path.realpath(manifest_path)
        if os.path.commonpath([branch_root, real_manifest]) != branch_root:
            failures.append("ATTEMPT_MANIFEST_OUTSIDE_BRANCH")
            continue
        if not _validate_raw_hash(real_manifest, ref.get("manifest_sha256")):
            failures.append("ATTEMPT_MANIFEST_HASH_INVALID")
            continue
        try:
            with open(real_manifest, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except (OSError, json.JSONDecodeError):
            failures.append("ATTEMPT_MANIFEST_INVALID")
            continue
        manifests.append(manifest)
        if manifest.get("schema_version") != ATTEMPT_SCHEMA_VERSION:
            failures.append("ATTEMPT_SCHEMA_INVALID")
        if manifest.get("attempt_number") != ref.get("attempt_number"):
            failures.append("ATTEMPT_NUMBER_BINDING_MISMATCH")
        for stream_key in ("raw_stdout", "raw_stderr"):
            stream_ref = manifest.get(stream_key)
            if not isinstance(stream_ref, dict):
                failures.append(f"{stream_key.upper()}_REFERENCE_MISSING")
                continue
            stream_path = os.path.join(os.path.dirname(real_manifest), stream_ref.get("path", ""))
            if not _validate_raw_hash(stream_path, stream_ref.get("sha256")):
                failures.append(f"{stream_key.upper()}_HASH_INVALID")

    delivered = metadata.get("response_delivered") is True
    final_classification = metadata.get("final_bridge_classification")
    response_exists = os.path.isfile(response) or os.path.isfile(response + ".sha256")
    if delivered:
        if not _validate_raw_hash(response):
            failures.append("DELIVERED_RESPONSE_ARTIFACT_REQUIRED")
    else:
        final_attempt = manifests[-1] if manifests else {}
        proven_pre_response = bool(
            final_classification == "PRE_RESPONSE_TRANSPORT_FAILURE"
            and final_attempt.get("final_bridge_classification") == "PRE_RESPONSE_TRANSPORT_FAILURE"
            and final_attempt.get("response_delivered") is False
            and metadata.get("is_infra_failure") is True
        )
        if not proven_pre_response:
            failures.append("MISSING_RESPONSE_WITHOUT_PROVEN_PRE_RESPONSE_FAILURE")
        if response_exists:
            failures.append("RESPONSE_ARTIFACT_PRESENT_FOR_PRE_RESPONSE_FAILURE")

    return {"custody_pass": not failures, "failure_reasons": failures}


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


def verify_gate5_preflight(a1_config: dict, root_dir: Optional[str] = None) -> dict:
    """
    Verifies that all frozen configuration bindings and candidate assets match
    their recorded SHA-256 hashes prior to executing the Gate 5 neutral probe (§A1.11).
    Fail-closed: if any check fails, returns preflight_pass=False.
    """
    if root_dir is None:
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    bindings = {}
    mismatches = []

    # Map config key -> relative file path from root_dir
    file_checks = [
        ("frozen_executor_config_sha256", os.path.join("tools", "executor_config.json")),
        ("frozen_executor_harness_sha256", os.path.join("tools", "executor_harness.py")),
        ("bridge_sha256", os.path.join("tools", "a1_surface_bridge.py")),
        ("bridge_tests_sha256", os.path.join("tests", "test_a1_surface_bridge.py")),
        ("bridge_activate_sha256", os.path.join("tools", "a1_activate.py")),
        ("target_preparer_sha256", os.path.join("tools", "prepare_blind_targets.py")),
        ("target_preparer_tests_sha256", os.path.join("tests", "test_prepare_blind_targets.py")),
        ("amendment_text_sha256", "AMENDMENT_A1_TRANSPORT.md"),
    ]

    for key, rel_path in file_checks:
        expected = a1_config.get(key)
        full_path = os.path.join(root_dir, rel_path)
        if not os.path.isfile(full_path):
            bindings[key] = {
                "expected": expected,
                "actual": None,
                "path": rel_path,
                "status": "FILE_NOT_FOUND"
            }
            mismatches.append(f"{key}: file not found at {rel_path}")
            continue

        actual = _sha256_file(full_path)
        match = (expected == actual)
        bindings[key] = {
            "expected": expected,
            "actual": actual,
            "path": rel_path,
            "status": "MATCH" if match else "MISMATCH"
        }
        if not match:
            mismatches.append(f"{key}: expected {expected}, got {actual}")

    # Primary surface binary check
    primary = a1_config.get("surfaces", {}).get("primary", {})
    bin_path = primary.get("executable_path")
    expected_bin_sha = primary.get("surface_binary_sha256")
    if bin_path:
        if not os.path.isfile(bin_path):
            bindings["surface_binary_sha256"] = {
                "expected": expected_bin_sha,
                "actual": None,
                "path": bin_path,
                "status": "FILE_NOT_FOUND"
            }
            mismatches.append(f"surface_binary: file not found at {bin_path}")
        else:
            actual_bin_sha = _sha256_file(bin_path)
            match = (expected_bin_sha == actual_bin_sha)
            bindings["surface_binary_sha256"] = {
                "expected": expected_bin_sha,
                "actual": actual_bin_sha,
                "path": bin_path,
                "status": "MATCH" if match else "MISMATCH"
            }
            if not match:
                mismatches.append(f"surface_binary_sha256: expected {expected_bin_sha}, got {actual_bin_sha}")

    preflight_pass = (len(mismatches) == 0)
    return {
        "preflight_pass": preflight_pass,
        "failure_reason": "; ".join(mismatches) if mismatches else None,
        "verified_bindings": bindings,
    }


def run_gate5_probe(
    model_id: str,
    a1_config: dict,
    artifact_dir: str,
    config: Optional[dict] = None,
    root_dir: Optional[str] = None,
    skip_preflight: bool = False,
) -> dict:
    """
    Execute the Gate 5 neutral inference probe for a given model_id (§A1.11).
    Contains ZERO blind theorem content.
    Fails closed if preflight configuration bindings do not match frozen state.
    Returns result dict with gate5_pass bool, preflight verification, and evidence fields.
    """
    if config is None:
        config = {}
    transcript: list = []

    # 1. Preflight config binding verification (§A1.11 fail-closed)
    preflight = None
    if not skip_preflight:
        preflight = verify_gate5_preflight(a1_config, root_dir)
        transcript.append({
            "event": "a1_gate5_preflight_verified",
            "preflight_pass": preflight["preflight_pass"],
            "failure_reason": preflight["failure_reason"],
        })
        if not preflight["preflight_pass"]:
            return {
                "gate5_pass": False,
                "failure_reason": f"PREFLIGHT_CONFIG_BINDING_MISMATCH: {preflight['failure_reason']}",
                "preflight": preflight,
                "transcript": transcript,
            }

    # 2. Neutral probe inference
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
        return {
            "gate5_pass": False,
            "failure_reason": "INFRA_FAILURE",
            "preflight": preflight,
            "transcript": transcript,
        }

    # Exact-match check: strip whitespace and optional code fences
    stripped = response_text.strip()
    for fence in ["```json", "```"]:
        if stripped.startswith(fence):
            stripped = stripped[len(fence):]
    if stripped.endswith("```"):
        stripped = stripped[:-3]
    stripped = stripped.strip()

    exact_match = (stripped == GATE5_EXPECTED_RESPONSE)
    gate5_result = {
        "gate5_pass": exact_match,
        "response_text": response_text,
        "response_stripped": stripped,
        "expected": GATE5_EXPECTED_RESPONSE,
        "exact_match": exact_match,
        "failure_reason": None if exact_match else "RESPONSE_NOT_EXACT_MATCH",
        "preflight": preflight,
        "transcript": transcript,
    }

    # Record Gate 5 receipt in artifact_dir
    os.makedirs(artifact_dir, exist_ok=True)
    receipt_path = os.path.join(artifact_dir, "gate5_receipt.json")
    try:
        with open(receipt_path, "w", encoding="utf-8") as f:
            json.dump(gate5_result, f, indent=2)
    except OSError:
        pass

    return gate5_result


def default_gate5_artifact_dir(a1_config: dict, root_dir: Optional[str] = None) -> str:
    """Resolve Gate 5 into the candidate execution namespace, never legacy r8 evidence."""
    if root_dir is None:
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    namespace = a1_config.get("execution_evidence_namespace")
    if not isinstance(namespace, str) or not namespace or os.path.isabs(namespace):
        raise ValueError("execution_evidence_namespace must be a non-empty relative path")
    candidate = os.path.realpath(os.path.join(
        root_dir, "evidence", "amendment_a1", namespace, "gate5"
    ))
    amendment_root = os.path.realpath(os.path.join(root_dir, "evidence", "amendment_a1"))
    if os.path.commonpath([candidate, amendment_root]) != amendment_root:
        raise ValueError("execution_evidence_namespace escapes amendment evidence root")
    return candidate


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
    parser.add_argument("--skip-preflight", action="store_true", help="Skip preflight config checks (testing only)")
    args = parser.parse_args()

    if args.gate5:
        cfg = _load_a1_config(args.a1_config)
        art_dir = args.artifact_dir or default_gate5_artifact_dir(cfg)
        result = run_gate5_probe(args.model, cfg, art_dir, skip_preflight=args.skip_preflight)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("gate5_pass") else 1)
    else:
        parser.print_help()
