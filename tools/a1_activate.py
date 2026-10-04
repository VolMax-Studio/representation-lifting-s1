#!/usr/bin/env python3
"""
tools/a1_activate.py

Amendment A1 activation shim for representation-lifting-s1.

Wraps the inference boundary, branch lifecycle, evidence sealing, and
receipt emission of tools/executor_harness.py WITHOUT modifying executor_harness.py.

Guarantees provided:
  1. Inference interception: call_model_api_with_resilience -> a1_call_surface.
  2. Branch artifact isolation (§A1.17, Finding F3):
     turn artifacts are partitioned by case and role:
     evidence/amendment_a1/artifacts/{case_id}/{role}/
     (requests/request_N.json, requests/surface_input_N.txt, responses/response_N.txt)
     Eliminates any cross-role or cross-case overwrite risk.
  3. Branch transcript sealing (§A1.7.3, Finding F1):
     upon completion of each role (D, S, L), its complete verbatim transcript
     is deterministically packaged into a .tar archive and its SHA-256 computed
     BEFORE the next branch begins.
  4. Receipt enrichment (§A1.17, Finding F1):
     joint blind execution receipts (and single-role receipts) are enriched with
     all twelve §A1.17 required custody fields:
     - transport_amendment: "A1"
     - transport_surface
     - model_identity_evidence
     - model_label_displayed
     - model_label_in_allowed_set
     - a1_transport_config_sha256
     - bridge_sha256
     - bridge_activate_sha256
     - inference_controls
     - system_role_handling
     - message_history_handling
     - branch_sealed_transcripts (per-branch archives and SHAs)
     - transcript_sealed_sha256

Usage:
    import tools.a1_activate as _  # side-effect: activates A1 layers
    from tools.executor_harness import ExecutorStateMachine, run_blind_case
    # All subsequent executions route through A1 with full custody guarantees.

Direct CLI usage:
    python3 tools/a1_activate.py --blind-case proofnet-108 targets/proofnet-108.lean claude-sonnet-4-6

Part of representation-lifting-s1 Amendment A1.
"""

import os
import sys
import json
import tarfile
import functools
from typing import Optional

import tools.executor_harness as _harness
from tools.a1_surface_bridge import (
    a1_call_surface,
    _load_a1_config,
    _sha256_file,
    emit_canonical_request,
    emit_surface_input,
    emit_response,
    emit_transport_metadata,
)

# ---------------------------------------------------------------------------
# Preserve original functions for test assertions & unwrapped operations
# ---------------------------------------------------------------------------
ORIGINAL_FN = _harness.call_model_api_with_resilience
ORIGINAL_SM_RUN = _harness.ExecutorStateMachine.run
ORIGINAL_RUN_BLIND_CASE = _harness.run_blind_case
ORIGINAL_RUN_CONTROL_CASE = _harness.run_control_case
ORIGINAL_RUN_CALIBRATION_FAMILY = _harness.run_calibration_family

# ---------------------------------------------------------------------------
# Global execution context
# ---------------------------------------------------------------------------
_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_A1_CONFIG_PATH: Optional[str] = None
_A1_CONFIG: Optional[dict] = None

_BASE_ARTIFACT_DIR: Optional[str] = None
_SEALED_DIR: Optional[str] = None
_RECEIPT_DIR: Optional[str] = None

_CURRENT_CASE_ID: Optional[str] = None
_CURRENT_ROLE: Optional[str] = None
_CURRENT_BRANCH_LABEL: Optional[str] = None

# Turn counter — keyed by (model_id, branch_artifact_dir)
_turn_counter: dict = {}

# Sealed branch transcripts — keyed by f"{case_id}::{branch_label}"
_BRANCH_SEALS: dict = {}


def _get_and_increment_turn(key: str) -> int:
    current = _turn_counter.get(key, 0)
    _turn_counter[key] = current + 1
    return current


def reset_turn_counter(key: Optional[str] = None) -> None:
    """Reset turn counter. If key is None, clear all."""
    if key is None:
        _turn_counter.clear()
    else:
        _turn_counter.pop(key, None)


def reset_branch_seals() -> None:
    """Reset recorded branch seals. Called between independent evaluation batches."""
    _BRANCH_SEALS.clear()


def configure(
    a1_config_path: Optional[str] = None,
    artifact_dir: Optional[str] = None,
    sealed_dir: Optional[str] = None,
    receipt_dir: Optional[str] = None,
) -> None:
    """
    Optionally configure custom paths for A1 activation.
    Defaults to canonical paths under evidence/amendment_a1/.
    """
    global _A1_CONFIG_PATH, _A1_CONFIG, _BASE_ARTIFACT_DIR, _SEALED_DIR, _RECEIPT_DIR
    _A1_CONFIG_PATH = a1_config_path
    _BASE_ARTIFACT_DIR = artifact_dir
    _SEALED_DIR = sealed_dir
    _RECEIPT_DIR = receipt_dir
    _A1_CONFIG = _load_a1_config(a1_config_path)


def _get_a1_config() -> dict:
    global _A1_CONFIG, _A1_CONFIG_PATH
    if _A1_CONFIG is None:
        _A1_CONFIG = _load_a1_config(_A1_CONFIG_PATH)
    return _A1_CONFIG


def _get_base_artifact_dir() -> str:
    global _BASE_ARTIFACT_DIR
    if _BASE_ARTIFACT_DIR is not None:
        return _BASE_ARTIFACT_DIR
    return os.path.join(_ROOT_DIR, "evidence", "amendment_a1", "artifacts")


def _get_sealed_dir() -> str:
    global _SEALED_DIR
    if _SEALED_DIR is not None:
        return _SEALED_DIR
    return os.path.join(_ROOT_DIR, "evidence", "amendment_a1", "sealed_transcripts")


def _get_receipt_dir() -> str:
    global _RECEIPT_DIR
    if _RECEIPT_DIR is not None:
        return _RECEIPT_DIR
    return os.path.join(_ROOT_DIR, "evidence", "amendment_a1", "receipts")


# ---------------------------------------------------------------------------
# Branch Evidence Sealing (§A1.7.3)
# ---------------------------------------------------------------------------

def seal_branch_transcript(branch_art_dir: str, seal_path: str) -> tuple[str, str, list[str]]:
    """
    Deterministically packages all turn artifacts from branch_art_dir into a .tar archive.
    Normalizes metadata (mtime=0, uid=0, gid=0) and sorts filenames.
    Computes SHA-256 of the archive and emits companion .sha256 file.
    Returns (seal_path, sha256_hex, file_list).
    """
    os.makedirs(os.path.dirname(os.path.abspath(seal_path)), exist_ok=True)
    file_list: list[str] = []
    if os.path.isdir(branch_art_dir):
        for root, dirs, files in os.walk(branch_art_dir):
            dirs.sort()
            for f in sorted(files):
                file_list.append(os.path.relpath(os.path.join(root, f), branch_art_dir))

    with tarfile.open(seal_path, "w") as tar:
        for rel in sorted(file_list):
            full = os.path.join(branch_art_dir, rel)
            tarinfo = tar.gettarinfo(full, arcname=rel)
            tarinfo.mtime = 0
            tarinfo.uid = 0
            tarinfo.gid = 0
            tarinfo.uname = ""
            tarinfo.gname = ""
            if tarinfo.isreg():
                with open(full, "rb") as f:
                    tar.addfile(tarinfo, f)
            else:
                tar.addfile(tarinfo)

    sha256 = _sha256_file(seal_path)
    sha_file = seal_path + ".sha256"
    with open(sha_file, "w", encoding="utf-8") as f:
        f.write(f"{sha256}  {os.path.basename(seal_path)}\n")

    return seal_path, sha256, file_list


# ---------------------------------------------------------------------------
# Patched call_model_api_with_resilience (Inference Boundary)
# ---------------------------------------------------------------------------

def _build_patched_inference_fn():
    @functools.wraps(ORIGINAL_FN)
    def _patched(model_id, messages, system_prompt, remaining_wallclock, config, transcript):
        cfg = _get_a1_config()
        base_dir = _get_base_artifact_dir()

        # Compute branch-isolated artifact directory
        case_id = _CURRENT_CASE_ID or "unspecified_case"
        branch_label = _CURRENT_BRANCH_LABEL or _CURRENT_ROLE or "unspecified_branch"
        branch_art_dir = os.path.join(base_dir, case_id, branch_label)
        os.makedirs(branch_art_dir, exist_ok=True)

        turn_key = f"{model_id}::{branch_art_dir}"
        turn_number = _get_and_increment_turn(turn_key)

        return a1_call_surface(
            model_id=model_id,
            messages=messages,
            system_prompt=system_prompt,
            remaining_wallclock=remaining_wallclock,
            config=config,
            transcript=transcript,
            a1_config=cfg,
            artifact_dir=branch_art_dir,
            turn_number=turn_number,
        )

    return _patched


# ---------------------------------------------------------------------------
# Patched ExecutorStateMachine.run (Branch Lifecycle & Sealing)
# ---------------------------------------------------------------------------

def _build_patched_sm_run():
    @functools.wraps(ORIGINAL_SM_RUN)
    def _wrapped_sm_run(self):
        global _CURRENT_ROLE, _CURRENT_CASE_ID, _CURRENT_BRANCH_LABEL
        role = self.role
        case_id = getattr(self, "_a1_case_id", None) or _CURRENT_CASE_ID
        if not case_id:
            # Derive case_id from target filename (e.g. proofnet-108.lean -> proofnet-108)
            case_id = os.path.splitext(os.path.basename(self.target_path))[0]

        target_name = os.path.basename(self.target_path) if self.target_path else ""
        if getattr(self, "_a1_branch_label", None):
            branch_label = self._a1_branch_label
        elif "_t1" in target_name:
            branch_label = f"{role}1"
        elif "_t2" in target_name:
            branch_label = f"{role}2"
        else:
            branch_label = role

        saved_role = _CURRENT_ROLE
        saved_case = _CURRENT_CASE_ID
        saved_branch = _CURRENT_BRANCH_LABEL
        _CURRENT_ROLE = role
        _CURRENT_CASE_ID = case_id
        _CURRENT_BRANCH_LABEL = branch_label

        base_dir = _get_base_artifact_dir()
        branch_art_dir = os.path.join(base_dir, case_id, branch_label)
        os.makedirs(branch_art_dir, exist_ok=True)

        orig_mock = self.mock_generator
        if orig_mock is not None:
            def _wrapped_mock(r, turn, msgs):
                cfg = _get_a1_config()
                primary_cfg = cfg.get("surfaces", {}).get("primary", {})
                
                sys_prompt = getattr(self, "system_prompt", None) or f"Representation-Lifting Executor Task for {r}"
                
                # Emit canonical request
                req_path, req_sha = emit_canonical_request(
                    branch_art_dir, turn, self.model_id, sys_prompt, msgs
                )
                
                # Emit surface input
                si_path, si_sha, _ = emit_surface_input(
                    branch_art_dir, turn, sys_prompt, msgs, primary_cfg
                )
                
                mock_out = orig_mock(r, turn, msgs)
                if isinstance(mock_out, tuple) and len(mock_out) >= 3:
                    resp_text, stop_reason, infra_fail = mock_out[:3]
                else:
                    resp_text, stop_reason, infra_fail = str(mock_out), "end_turn", False
                
                mock_meta = {
                    "model_returned": self.model_id if not infra_fail else None,
                    "assistant_model": self.model_id if not infra_fail else None,
                    "tools": [],
                    "mcp_servers": [],
                    "permission_mode": "mock",
                    "stop_reason": stop_reason or ("end_turn" if not infra_fail else "INFRA_FAIL"),
                    "is_infra_failure": bool(infra_fail),
                }
                if isinstance(mock_out, tuple) and len(mock_out) == 4 and isinstance(mock_out[3], dict):
                    mock_meta.update(mock_out[3])
                
                emit_transport_metadata(branch_art_dir, turn, mock_meta)
                
                if not infra_fail:
                    emit_response(branch_art_dir, turn, resp_text)
                
                return resp_text, stop_reason, infra_fail
            
            self.mock_generator = _wrapped_mock

        try:
            res = ORIGINAL_SM_RUN(self)
        finally:
            self.mock_generator = orig_mock

            # --- Branch evidence sealing (§A1.7.3) ---
            # Executed immediately upon branch completion, before next branch starts
            sealed_dir = _get_sealed_dir()
            seal_archive_path = os.path.join(
                sealed_dir, f"sealed_{case_id}_{branch_label}_{self.model_id}.tar"
            )
            tar_path, tar_sha, file_list = seal_branch_transcript(branch_art_dir, seal_archive_path)

            seal_info = {
                "archive_path": tar_path,
                "sha256": tar_sha,
                "file_count": len(file_list),
                "files": file_list,
            }
            _BRANCH_SEALS[f"{case_id}::{branch_label}"] = seal_info

            # Enrich the single-role receipt inside state machine
            if hasattr(self, "receipt") and isinstance(self.receipt, dict):
                self.receipt["transport_amendment"] = "A1"
                self.receipt["branch_sealed_transcript"] = tar_path
                self.receipt["branch_sealed_transcript_sha256"] = tar_sha
                if getattr(self, "save_receipt_path", None):
                    try:
                        with open(self.save_receipt_path, "w", encoding="utf-8") as f:
                            json.dump(self.receipt, f, indent=2)
                    except OSError:
                        pass

            _CURRENT_ROLE = saved_role
            _CURRENT_CASE_ID = saved_case
            _CURRENT_BRANCH_LABEL = saved_branch

        return res

    return _wrapped_sm_run


# ---------------------------------------------------------------------------
# Receipt Enrichment Helpers (§A1.17 / Findings F5, F6, F7)
# ---------------------------------------------------------------------------

def _extract_observed_model_evidence(case_id: str, branch_labels: list[str]) -> tuple:
    """
    Inspects transport_metadata_*.json across all specified branch artifact directories
    for the given case_id.
    Returns: (displayed_label, in_allowed_set, observed_models_list)
    """
    cfg = _get_a1_config()
    primary = cfg.get("surfaces", {}).get("primary", {})
    allowed_labels = set(primary.get("allowed_model_labels", []))
    base_dir = _get_base_artifact_dir()

    observed_models = []
    for blabel in branch_labels:
        bdir = os.path.join(base_dir, case_id, blabel)
        for sub in ["transport_metadata", "metadata"]:
            meta_dir = os.path.join(bdir, sub)
            if os.path.isdir(meta_dir):
                for fname in sorted(os.listdir(meta_dir)):
                    if fname.startswith("transport_metadata_") and fname.endswith(".json") and not fname.endswith(".sha256"):
                        mpath = os.path.join(meta_dir, fname)
                        try:
                            with open(mpath, "r", encoding="utf-8") as f:
                                mdata = json.load(f)
                                ret_model = mdata.get("model_returned")
                                if ret_model:
                                    observed_models.append(ret_model)
                        except Exception:
                            pass

    unique_observed = sorted(list(set(observed_models)))
    if not unique_observed:
        return "UNOBSERVED", False, []

    displayed = unique_observed[0] if len(unique_observed) == 1 else unique_observed
    in_allowed = bool(unique_observed and all(m in allowed_labels for m in unique_observed))
    return displayed, in_allowed, unique_observed


def _enrich_receipt(receipt: dict, case_id: str, model_id: str, branch_labels: list[str]) -> dict:
    """Enrich execution receipt with all twelve §A1.17 required custody fields."""
    cfg = _get_a1_config()
    primary = cfg.get("surfaces", {}).get("primary", {})

    cfg_path = _A1_CONFIG_PATH or os.path.join(
        _ROOT_DIR, "evidence", "amendment_a1", "a1_transport_config.json"
    )
    bridge_path = os.path.join(_ROOT_DIR, "tools", "a1_surface_bridge.py")
    activate_path = os.path.join(_ROOT_DIR, "tools", "a1_activate.py")

    displayed, in_allowed, observed_models = _extract_observed_model_evidence(case_id, branch_labels)

    branch_seals = {bl: _BRANCH_SEALS.get(f"{case_id}::{bl}") for bl in branch_labels}
    seal_hashes = {bl: (branch_seals[bl].get("sha256") if branch_seals.get(bl) else None) for bl in branch_labels}

    receipt["transport_amendment"] = "A1"
    receipt["transport_surface"] = primary.get("surface_type", "claude-code-cli")
    receipt["surface_metadata"] = {
        "type": primary.get("surface_type", "claude-code-cli"),
        "version": primary.get("surface_version", ""),
        "plan_tier": primary.get("plan_tier", "Pro"),
    }
    receipt["plan_tier"] = primary.get("plan_tier", "Pro")
    receipt["model_identity_evidence"] = primary.get(
        "model_identity_evidence", "CLAUDE_CODE_STREAM_JSON_INIT_MODEL"
    )
    receipt["model_label_displayed"] = displayed
    receipt["model_label_in_allowed_set"] = in_allowed
    receipt["observed_models"] = observed_models
    receipt["a1_transport_config_sha256"] = _sha256_file(cfg_path) if os.path.isfile(cfg_path) else None
    receipt["bridge_sha256"] = _sha256_file(bridge_path) if os.path.isfile(bridge_path) else None
    receipt["bridge_activate_sha256"] = _sha256_file(activate_path) if os.path.isfile(activate_path) else None
    receipt["inference_controls"] = primary.get("inference_controls_pinned", {})
    receipt["system_role_handling"] = primary.get("system_role_handling", "NATIVE_SYSTEM_MESSAGE")
    receipt["message_history_handling"] = primary.get(
        "message_history_handling", "DEGRADED_HISTORY_FLATTENED_TO_USER_CONTENT"
    )
    receipt["branch_sealed_transcripts"] = branch_seals
    receipt["transcript_sealed_sha256"] = seal_hashes

    return receipt


def _enrich_blind_receipt(receipt: dict, case_id: str, model_id: str) -> dict:
    """Enrich blind execution receipt with all twelve §A1.17 required fields."""
    return _enrich_receipt(receipt, case_id, model_id, ["D", "S", "L"])


# ---------------------------------------------------------------------------
# Patched run_blind_case (Joint Execution & Receipt Enrichment)
# ---------------------------------------------------------------------------

def _build_patched_run_blind_case():
    @functools.wraps(ORIGINAL_RUN_BLIND_CASE)
    def _wrapped_run_blind_case(
        case_id: str,
        target_path: str,
        model_id: str,
        admissibility_path: str | None = None,
        mock_generator=None,
        on_d_complete_callback=None,
        run_tmp_root: str | None = None,
    ) -> dict:
        global _CURRENT_CASE_ID
        saved_case = _CURRENT_CASE_ID
        _CURRENT_CASE_ID = case_id

        try:
            blind_report = ORIGINAL_RUN_BLIND_CASE(
                case_id=case_id,
                target_path=target_path,
                model_id=model_id,
                admissibility_path=admissibility_path,
                mock_generator=mock_generator,
                on_d_complete_callback=on_d_complete_callback,
                run_tmp_root=run_tmp_root,
            )

            # Enrich the joint receipt with all §A1.17 fields
            enriched = _enrich_blind_receipt(blind_report, case_id, model_id)

            # Persist enriched receipt to canonical locations
            tools_dir = _harness.TOOLS_DIR
            receipt_targets = [
                os.path.join(tools_dir, f"execution_receipt_blind_{case_id}_{model_id}.json"),
                os.path.join(tools_dir, f"execution_receipt_blind_{case_id}.json"),
                os.path.join(_get_receipt_dir(), f"execution_receipt_blind_{case_id}_{model_id}.json"),
            ]
            for rpath in receipt_targets:
                try:
                    os.makedirs(os.path.dirname(os.path.abspath(rpath)), exist_ok=True)
                    with open(rpath, "w", encoding="utf-8") as f:
                        json.dump(enriched, f, indent=2)
                except OSError:
                    pass

            return enriched
        finally:
            _CURRENT_CASE_ID = saved_case

    return _wrapped_run_blind_case


# ---------------------------------------------------------------------------
# Patched run_control_case and run_calibration_family
# ---------------------------------------------------------------------------

def _build_patched_run_control_case():
    @functools.wraps(ORIGINAL_RUN_CONTROL_CASE)
    def _wrapped_run_control_case(
        model_id: str,
        target_path: Optional[str] = None,
        stub_path: Optional[str] = None,
        admissibility_path: Optional[str] = None,
        mock_generator=None,
        on_d_complete_callback=None,
        run_tmp_root: Optional[str] = None,
        receipt_out_path: Optional[str] = None,
    ) -> dict:
        global _CURRENT_CASE_ID
        saved_case = _CURRENT_CASE_ID
        _CURRENT_CASE_ID = "control"

        try:
            report = ORIGINAL_RUN_CONTROL_CASE(
                model_id=model_id,
                target_path=target_path,
                stub_path=stub_path,
                admissibility_path=admissibility_path,
                mock_generator=mock_generator,
                on_d_complete_callback=on_d_complete_callback,
                run_tmp_root=run_tmp_root,
                receipt_out_path=receipt_out_path,
            )

            # Enrich joint control receipt with all §A1.17 fields (D, L branches)
            enriched = _enrich_receipt(report, "control", model_id, ["D", "L"])

            tools_dir = _harness.TOOLS_DIR
            receipt_targets = [
                receipt_out_path or os.path.join(tools_dir, f"execution_receipt_control_{model_id}.json"),
                os.path.join(tools_dir, "execution_receipt_control.json"),
                os.path.join(_get_receipt_dir(), f"execution_receipt_control_{model_id}.json"),
                os.path.join(_get_receipt_dir(), "execution_receipt_control.json"),
            ]
            for rpath in receipt_targets:
                if rpath:
                    try:
                        os.makedirs(os.path.dirname(os.path.abspath(rpath)), exist_ok=True)
                        with open(rpath, "w", encoding="utf-8") as f:
                            json.dump(enriched, f, indent=2)
                    except OSError:
                        pass

            return enriched
        finally:
            _CURRENT_CASE_ID = saved_case

    return _wrapped_run_control_case


def _build_patched_run_calibration_family():
    @functools.wraps(ORIGINAL_RUN_CALIBRATION_FAMILY)
    def _wrapped_run_calibration_family(
        family_name: str,
        model_id: str,
        mock_generator=None,
        on_d_complete_callback=None,
        run_tmp_root: Optional[str] = None,
    ) -> dict:
        global _CURRENT_CASE_ID
        saved_case = _CURRENT_CASE_ID
        case_id = f"calibration_{family_name}"
        _CURRENT_CASE_ID = case_id

        try:
            report = ORIGINAL_RUN_CALIBRATION_FAMILY(
                family_name=family_name,
                model_id=model_id,
                mock_generator=mock_generator,
                on_d_complete_callback=on_d_complete_callback,
                run_tmp_root=run_tmp_root,
            )

            # Enrich joint calibration receipt with all §A1.17 fields (D1, D2, S1, L1, S2, L2 branches)
            enriched = _enrich_receipt(
                report, case_id, model_id, ["D1", "D2", "S1", "L1", "S2", "L2"]
            )

            tools_dir = _harness.TOOLS_DIR
            receipt_targets = [
                os.path.join(tools_dir, f"execution_receipt_calibration_{family_name}_{model_id}.json"),
                os.path.join(tools_dir, f"execution_receipt_calibration_{family_name}.json"),
                os.path.join(_get_receipt_dir(), f"execution_receipt_calibration_{family_name}_{model_id}.json"),
                os.path.join(_get_receipt_dir(), f"execution_receipt_calibration_{family_name}.json"),
            ]
            for rpath in receipt_targets:
                try:
                    os.makedirs(os.path.dirname(os.path.abspath(rpath)), exist_ok=True)
                    with open(rpath, "w", encoding="utf-8") as f:
                        json.dump(enriched, f, indent=2)
                except OSError:
                    pass

            return enriched
        finally:
            _CURRENT_CASE_ID = saved_case

    return _wrapped_run_calibration_family


# ---------------------------------------------------------------------------
# Apply patches at import time
# ---------------------------------------------------------------------------
_PATCHED_FN = _build_patched_inference_fn()
_PATCHED_SM_RUN = _build_patched_sm_run()
_PATCHED_RUN_BLIND_CASE = _build_patched_run_blind_case()
_PATCHED_RUN_CONTROL_CASE = _build_patched_run_control_case()
_PATCHED_RUN_CALIBRATION_FAMILY = _build_patched_run_calibration_family()

_harness.call_model_api_with_resilience = _PATCHED_FN
_harness.ExecutorStateMachine.run = _PATCHED_SM_RUN
_harness.run_blind_case = _PATCHED_RUN_BLIND_CASE
_harness.run_control_case = _PATCHED_RUN_CONTROL_CASE
_harness.run_calibration_family = _PATCHED_RUN_CALIBRATION_FAMILY

# Confirm all patches are live
assert _harness.call_model_api_with_resilience is _PATCHED_FN, \
    "A1 activation failed: call_model_api_with_resilience was not patched"
assert _harness.ExecutorStateMachine.run is _PATCHED_SM_RUN, \
    "A1 activation failed: ExecutorStateMachine.run was not patched"
assert _harness.run_blind_case is _PATCHED_RUN_BLIND_CASE, \
    "A1 activation failed: run_blind_case was not patched"
assert _harness.run_control_case is _PATCHED_RUN_CONTROL_CASE, \
    "A1 activation failed: run_control_case was not patched"
assert _harness.run_calibration_family is _PATCHED_RUN_CALIBRATION_FAMILY, \
    "A1 activation failed: run_calibration_family was not patched"

if __name__ == "__main__":
    _harness.main()
