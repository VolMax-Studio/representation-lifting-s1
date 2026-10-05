#!/usr/bin/env python3
"""Non-billed Codex subscription command adapter.

Reads a provider-neutral request envelope on stdin and emits exactly one
provider-neutral result envelope on stdout.  Authentication is owned by the
installed Codex CLI (``codex login``); this adapter neither reads nor accepts
direct API keys.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.execution_adapter import REQUEST_SCHEMA, RESULT_SCHEMA, flatten_request


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def _find_rollout(thread_id: str, deadline: float) -> Path | None:
    sessions = _codex_home() / "sessions"
    while time.monotonic() < deadline:
        for candidate in sessions.glob("*/*/*/*.jsonl"):
            if thread_id in candidate.name:
                return candidate
        time.sleep(0.05)
    return None


def _identity_from_rollout(path: Path, thread_id: str) -> dict:
    session_meta = None
    turn_context = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "session_meta" and event.get("payload", {}).get("id") == thread_id:
            session_meta = event.get("payload", {})
        elif event.get("type") == "turn_context":
            turn_context = event.get("payload", {})
    if not session_meta or not turn_context:
        raise RuntimeError("CODEX_IDENTITY_EVIDENCE_MISSING")
    return {
        "schema_version": "representation-lifting-codex-identity-evidence/v1",
        "thread_id": thread_id,
        "model": turn_context.get("model"),
        "model_provider": session_meta.get("model_provider"),
        "cli_version": session_meta.get("cli_version"),
        "source": session_meta.get("source"),
        "rollout_filename": path.name,
    }


def _emit(payload: dict) -> int:
    sys.stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


def main() -> int:
    started = utc_now()
    request = json.load(sys.stdin)
    declared = request.get("declared_model_id")
    if request.get("schema_version") != REQUEST_SCHEMA or not isinstance(declared, str) or not declared:
        raise RuntimeError("INVALID_PROVIDER_NEUTRAL_REQUEST")
    executable = shutil.which("codex")
    if not executable:
        raise RuntimeError("CODEX_CLI_NOT_FOUND")
    turn_dir_raw = os.environ.get("EXECUTION_ADAPTER_TURN_DIR")
    if not turn_dir_raw:
        raise RuntimeError("EXECUTION_ADAPTER_TURN_DIR_MISSING")
    turn_dir = Path(turn_dir_raw)

    prompt = flatten_request(request.get("system_prompt", ""), request.get("messages", []))
    child_env = os.environ.copy()
    stripped_direct_api_variables = []
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        if child_env.pop(name, None) is not None:
            stripped_direct_api_variables.append(name)
    app_tools_pipe_removed = child_env.pop("CODEX_APP_TOOLS_PIPE_PATH", None) is not None
    auth = subprocess.run(
        [executable, "login", "status"], text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False, env=child_env,
    )
    auth_status = auth.stdout.strip()
    if auth.returncode != 0 or "Logged in using ChatGPT" not in auth_status:
        raise RuntimeError("CODEX_CHATGPT_SUBSCRIPTION_AUTH_NOT_ACTIVE")
    with tempfile.TemporaryDirectory(prefix="representation_lifting_codex_") as clean_cwd:
        response_path = Path(clean_cwd) / "last_message.txt"
        command = [
            executable,
            "--disable", "shell_tool",
            "--disable", "plugins",
            "--disable", "apps",
            "--disable", "remote_plugin",
            "-c", 'web_search="disabled"',
            "-a", "never", "exec",
            "--ignore-user-config", "--ignore-rules", "--json",
            "-s", "read-only", "-m", declared, "--skip-git-repo-check",
            "-C", clean_cwd, "-o", str(response_path), "-",
        ]
        completed = subprocess.run(
            command, input=prompt, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=False, env=child_env,
        )
        events_bytes = completed.stdout.encode("utf-8")
        (turn_dir / "codex_events.jsonl").write_bytes(events_bytes)
        if completed.stderr:
            sys.stderr.write(completed.stderr)

        thread_id = None
        tool_event_types = []
        for raw in completed.stdout.splitlines():
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "thread.started":
                thread_id = event.get("thread_id")
            item = event.get("item")
            if isinstance(item, dict):
                item_type = item.get("type")
                if item_type not in (None, "agent_message", "reasoning"):
                    tool_event_types.append(str(item_type))

        base_metadata = {
            "surface": "Codex CLI via ChatGPT subscription authentication",
            "billing_mode": "SUBSCRIPTION_AUTH_NO_DIRECT_API_KEY",
            "auth_status": auth_status,
            "direct_api_environment_stripped": sorted(stripped_direct_api_variables),
            "codex_cli_exit_code": completed.returncode,
            "thread_id": thread_id,
            "user_config_ignored": True,
            "web_search_disabled": True,
            "plugins_disabled": True,
            "app_tools_pipe_removed": app_tools_pipe_removed,
            "transport_environment_stripped": (
                ["CODEX_APP_TOOLS_PIPE_PATH"] if app_tools_pipe_removed else []
            ),
            "shell_tool_disabled": True,
            "tool_event_types": sorted(set(tool_event_types)),
        }
        if tool_event_types:
            raise RuntimeError("CODEX_TOOL_EVENT_DETECTED:" + ",".join(sorted(set(tool_event_types))))
        if completed.returncode != 0 or not thread_id or not response_path.is_file():
            return _emit({
                "schema_version": RESULT_SCHEMA,
                "response_text": "",
                "observed_model_id": None,
                "delivery_status": "NOT_DELIVERED",
                "started_at_utc": started,
                "completed_at_utc": utc_now(),
                "transport_metadata": {
                    **base_metadata,
                    "stop_reason": "CLI_ERROR",
                    "evidence_files": {"codex_events.jsonl": sha256_bytes(events_bytes)},
                },
            })

        rollout = _find_rollout(thread_id, time.monotonic() + 5.0)
        if rollout is None:
            raise RuntimeError("CODEX_ROLLOUT_NOT_FOUND")
        identity = _identity_from_rollout(rollout, thread_id)
        identity_bytes = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        (turn_dir / "codex_identity_evidence.json").write_bytes(identity_bytes)
        observed = identity.get("model")
        if observed != declared:
            raise RuntimeError(f"CODEX_MODEL_IDENTITY_MISMATCH:{declared}:{observed}")
        response = response_path.read_text(encoding="utf-8")
        return _emit({
            "schema_version": RESULT_SCHEMA,
            "response_text": response,
            "observed_model_id": observed,
            "delivery_status": "DELIVERED",
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "transport_metadata": {
                **base_metadata,
                "model_provider": identity.get("model_provider"),
                "codex_cli_version": identity.get("cli_version"),
                "identity_source": "codex rollout session_meta + turn_context",
                "stop_reason": "end_turn",
                "evidence_files": {
                    "codex_events.jsonl": sha256_bytes(events_bytes),
                    "codex_identity_evidence.json": sha256_bytes(identity_bytes),
                },
            },
        })


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        raise SystemExit(2)
