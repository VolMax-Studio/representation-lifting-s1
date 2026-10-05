#!/usr/bin/env python3
"""Provider-neutral execution boundary and custody artifacts.

Adapters transport an exact request to a model surface.  They do not decide
scientific roles, construct prompts, verify Lean, score results, or interpret
outcomes.  Credentials, subscriptions, and billing remain outside this repo.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONTRACT_SCHEMA = "representation-lifting-execution-adapter/v1"
REQUEST_SCHEMA = "representation-lifting-model-request/v1"
RESULT_SCHEMA = "representation-lifting-model-result/v1"
DELIVERY_STATES = {"DELIVERED", "NOT_DELIVERED", "AMBIGUOUS"}
ADAPTER_KINDS = {"manual-relay", "command"}
SECRET_MARKERS = ("api_key", "apikey", "access_token", "secret", "password", "bearer")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _contains_secret(value: Any, path: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            lowered = str(key).lower()
            if any(marker in lowered for marker in SECRET_MARKERS) and item not in (None, "", False):
                findings.append(key_path)
            findings.extend(_contains_secret(item, key_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_contains_secret(item, f"{path}[{index}]"))
    return findings


def validate_adapter_config(config: dict) -> dict:
    """Fail closed on an unstable, provider-bound, or secret-bearing contract."""
    errors: list[str] = []
    if config.get("schema_version") != CONTRACT_SCHEMA:
        errors.append(f"schema_version must be {CONTRACT_SCHEMA}")
    adapter_id = config.get("adapter_id")
    if not isinstance(adapter_id, str) or not adapter_id.strip():
        errors.append("adapter_id must be a non-empty string")
    kind = config.get("kind")
    if kind not in ADAPTER_KINDS:
        errors.append(f"kind must be one of {sorted(ADAPTER_KINDS)}")
    if config.get("trust_role") != "TRANSPORT_ONLY_NOT_TRUST_ROOT":
        errors.append("trust_role must be TRANSPORT_ONLY_NOT_TRUST_ROOT")
    if config.get("credentials") != "OPERATOR_SUPPLIED_OUTSIDE_REPOSITORY":
        errors.append("credentials policy must keep credentials outside the repository")
    if config.get("direct_api_required") is not False:
        errors.append("direct_api_required must be false")
    if config.get("request_schema") != REQUEST_SCHEMA:
        errors.append(f"request_schema must be {REQUEST_SCHEMA}")
    if config.get("result_schema") != RESULT_SCHEMA:
        errors.append(f"result_schema must be {RESULT_SCHEMA}")
    secret_paths = _contains_secret(config)
    if secret_paths:
        errors.append("credential-like values are forbidden at: " + ", ".join(secret_paths))
    if kind == "command":
        command = config.get("command")
        if not isinstance(command, list) or not command or not all(isinstance(v, str) and v for v in command):
            errors.append("command adapter requires a non-empty argv list")
    return {"contract_pass": not errors, "errors": errors}


@dataclass(frozen=True)
class ModelRequest:
    execution_id: str
    turn_number: int
    declared_model_id: str
    system_prompt: str
    messages: list[dict]
    created_at_utc: str

    def envelope(self) -> dict:
        return {
            "schema_version": REQUEST_SCHEMA,
            "execution_id": self.execution_id,
            "turn_number": self.turn_number,
            "declared_model_id": self.declared_model_id,
            "system_prompt": self.system_prompt,
            "messages": self.messages,
            "created_at_utc": self.created_at_utc,
        }


@dataclass(frozen=True)
class ModelResult:
    response_text: str
    declared_model_id: str
    observed_model_id: str | None
    delivery_status: str
    started_at_utc: str
    completed_at_utc: str
    transport_metadata: dict

    def validate(self) -> None:
        if self.delivery_status not in DELIVERY_STATES:
            raise ValueError(f"invalid delivery_status: {self.delivery_status}")
        if self.delivery_status == "DELIVERED" and self.observed_model_id != self.declared_model_id:
            raise ValueError(
                "delivered response model identity mismatch: "
                f"declared={self.declared_model_id!r}, observed={self.observed_model_id!r}"
            )
        if self.delivery_status != "DELIVERED" and self.response_text:
            raise ValueError("non-delivered result cannot contain response bytes")

    def envelope(self, request_sha256: str, response_sha256: str | None) -> dict:
        return {
            "schema_version": RESULT_SCHEMA,
            "declared_model_id": self.declared_model_id,
            "observed_model_id": self.observed_model_id,
            "delivery_status": self.delivery_status,
            "started_at_utc": self.started_at_utc,
            "completed_at_utc": self.completed_at_utc,
            "request_sha256": request_sha256,
            "response_sha256": response_sha256,
            "transport_metadata": self.transport_metadata,
        }


class ExecutionAdapter(ABC):
    def __init__(self, config: dict):
        validation = validate_adapter_config(config)
        if not validation["contract_pass"]:
            raise ValueError("invalid adapter contract: " + "; ".join(validation["errors"]))
        self.config = config

    @abstractmethod
    def transport(self, request: ModelRequest, turn_dir: Path, timeout_seconds: float) -> ModelResult:
        raise NotImplementedError

    def execute(self, request: ModelRequest, turn_dir: Path, timeout_seconds: float) -> ModelResult:
        turn_dir.mkdir(parents=True, exist_ok=False)
        request_path = turn_dir / "request.json"
        request_bytes = canonical_json_bytes(request.envelope())
        request_path.write_bytes(request_bytes)
        request_sha = sha256_bytes(request_bytes)
        (turn_dir / "request.json.sha256").write_text(request_sha + "\n", encoding="utf-8")

        result = self.transport(request, turn_dir, timeout_seconds)
        result.validate()
        response_sha = None
        if result.delivery_status == "DELIVERED":
            response_bytes = result.response_text.encode("utf-8")
            response_path = turn_dir / "response.txt"
            response_path.write_bytes(response_bytes)
            response_sha = sha256_bytes(response_bytes)
            (turn_dir / "response.txt.sha256").write_text(response_sha + "\n", encoding="utf-8")

        result_envelope = result.envelope(request_sha, response_sha)
        result_bytes = canonical_json_bytes(result_envelope)
        (turn_dir / "result.json").write_bytes(result_bytes)
        (turn_dir / "result.json.sha256").write_text(sha256_bytes(result_bytes) + "\n", encoding="utf-8")
        return result


class ManualRelayAdapter(ExecutionAdapter):
    """Faithful operator-courier relay using only files and a chosen web/local surface."""

    def transport(self, request: ModelRequest, turn_dir: Path, timeout_seconds: float) -> ModelResult:
        relay_path = turn_dir / "relay_input.txt"
        relay_text = flatten_request(request.system_prompt, request.messages)
        relay_path.write_text(relay_text, encoding="utf-8")
        (turn_dir / "relay_input.txt.sha256").write_text(sha256_file(relay_path) + "\n", encoding="utf-8")
        incoming = turn_dir / "incoming_response.txt"
        identity = turn_dir / "incoming_identity.json"
        started = utc_now()
        print(
            "\n[MANUAL MODEL RELAY]\n"
            f"Copy {relay_path} verbatim to the declared model surface.\n"
            f"Save the complete response verbatim to {incoming}.\n"
            f"Save identity evidence as JSON to {identity}:\n"
            f'{{"observed_model_id":"{request.declared_model_id}","surface":"operator-observed"}}\n',
            flush=True,
        )
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if incoming.is_file() and identity.is_file():
                response = incoming.read_text(encoding="utf-8")
                identity_data = json.loads(identity.read_text(encoding="utf-8"))
                return ModelResult(
                    response_text=response,
                    declared_model_id=request.declared_model_id,
                    observed_model_id=identity_data.get("observed_model_id"),
                    delivery_status="DELIVERED",
                    started_at_utc=started,
                    completed_at_utc=utc_now(),
                    transport_metadata={
                        "adapter_id": self.config["adapter_id"],
                        "adapter_kind": "manual-relay",
                        "surface": identity_data.get("surface", "operator-observed"),
                        "identity_evidence_sha256": sha256_file(identity),
                        "operator_courier": True,
                    },
                )
            time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))
        return ModelResult(
            response_text="",
            declared_model_id=request.declared_model_id,
            observed_model_id=None,
            delivery_status="NOT_DELIVERED",
            started_at_utc=started,
            completed_at_utc=utc_now(),
            transport_metadata={"adapter_id": self.config["adapter_id"], "timeout": True},
        )


class CommandAdapter(ExecutionAdapter):
    """Run an operator-selected CLI/local adapter speaking JSON over stdin/stdout."""

    def transport(self, request: ModelRequest, turn_dir: Path, timeout_seconds: float) -> ModelResult:
        started = utc_now()
        env = os.environ.copy()
        env["EXECUTION_ADAPTER_TURN_DIR"] = str(turn_dir.resolve())
        completed = subprocess.run(
            self.config["command"],
            input=canonical_json_bytes(request.envelope()),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
            env=env,
        )
        stderr_path = turn_dir / "adapter.stderr"
        stderr_path.write_bytes(completed.stderr)
        (turn_dir / "adapter.stderr.sha256").write_text(sha256_file(stderr_path) + "\n", encoding="utf-8")
        if completed.returncode != 0:
            return ModelResult(
                response_text="", declared_model_id=request.declared_model_id,
                observed_model_id=None, delivery_status="NOT_DELIVERED",
                started_at_utc=started, completed_at_utc=utc_now(),
                transport_metadata={"adapter_id": self.config["adapter_id"], "exit_code": completed.returncode},
            )
        payload = json.loads(completed.stdout.decode("utf-8"))
        if payload.get("schema_version") != RESULT_SCHEMA:
            raise ValueError("command adapter returned the wrong result schema")
        return ModelResult(
            response_text=payload.get("response_text", ""),
            declared_model_id=request.declared_model_id,
            observed_model_id=payload.get("observed_model_id"),
            delivery_status=payload.get("delivery_status", "AMBIGUOUS"),
            started_at_utc=payload.get("started_at_utc", started),
            completed_at_utc=payload.get("completed_at_utc", utc_now()),
            transport_metadata={
                "adapter_id": self.config["adapter_id"],
                "adapter_kind": "command",
                "exit_code": completed.returncode,
                **payload.get("transport_metadata", {}),
            },
        )


def flatten_request(system_prompt: str, messages: list[dict]) -> str:
    parts = [
        "=== PROTOCOL SYSTEM INSTRUCTIONS (DO NOT MODIFY) ===", system_prompt,
        "=== END PROTOCOL SYSTEM INSTRUCTIONS ===", "=== CONVERSATION HISTORY ===",
    ]
    for index, message in enumerate(messages, start=1):
        role = str(message.get("role", "unknown")).upper()
        parts.extend([f"[Message {index} - {role}]", str(message.get("content", ""))])
    parts.append("=== END CONVERSATION HISTORY ===")
    return "\n\n".join(parts) + "\n"


def build_adapter(config: dict) -> ExecutionAdapter:
    kind = config.get("kind")
    if kind == "manual-relay":
        return ManualRelayAdapter(config)
    if kind == "command":
        return CommandAdapter(config)
    raise ValueError(f"unsupported adapter kind: {kind!r}")


def verify_turn_custody(turn_dir: Path) -> dict:
    errors: list[str] = []
    for name in ("request.json", "result.json"):
        path = turn_dir / name
        sidecar = turn_dir / f"{name}.sha256"
        if not path.is_file() or not sidecar.is_file():
            errors.append(f"missing {name} or hash sidecar")
        elif sidecar.read_text(encoding="utf-8").strip() != sha256_file(path):
            errors.append(f"hash mismatch: {name}")
    result = None
    if (turn_dir / "result.json").is_file():
        result = json.loads((turn_dir / "result.json").read_text(encoding="utf-8"))
        request = json.loads((turn_dir / "request.json").read_text(encoding="utf-8")) \
            if (turn_dir / "request.json").is_file() else {}
        if (turn_dir / "request.json").is_file():
            if result.get("request_sha256") != sha256_file(turn_dir / "request.json"):
                errors.append("result request_sha256 mismatch")
        if not result.get("started_at_utc") or not result.get("completed_at_utc"):
            errors.append("transport timestamps missing")
        if result.get("delivery_status") == "DELIVERED":
            if result.get("declared_model_id") != request.get("declared_model_id"):
                errors.append("declared model identity mismatch")
            if result.get("observed_model_id") != result.get("declared_model_id"):
                errors.append("observed model identity mismatch")
            response = turn_dir / "response.txt"
            sidecar = turn_dir / "response.txt.sha256"
            if not response.is_file() or not sidecar.is_file():
                errors.append("delivered response bytes or hash sidecar missing")
            elif sidecar.read_text(encoding="utf-8").strip() != sha256_file(response):
                errors.append("hash mismatch: response.txt")
            elif result.get("response_sha256") != sha256_file(response):
                errors.append("result response_sha256 mismatch")
        evidence_files = result.get("transport_metadata", {}).get("evidence_files", {})
        if not isinstance(evidence_files, dict):
            errors.append("transport evidence_files must be an object")
        else:
            for name, expected in evidence_files.items():
                if Path(name).name != name:
                    errors.append(f"unsafe transport evidence filename: {name}")
                    continue
                evidence = turn_dir / name
                if not evidence.is_file():
                    errors.append(f"missing transport evidence: {name}")
                elif sha256_file(evidence) != expected:
                    errors.append(f"transport evidence hash mismatch: {name}")
    return {"custody_pass": not errors, "errors": errors, "delivery_status": (result or {}).get("delivery_status")}
