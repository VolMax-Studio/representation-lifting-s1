#!/usr/bin/env python3
"""
tools/a1_activate.py

Amendment A1 activation shim for representation-lifting-s1.

Monkey-patches executor_harness.call_model_api_with_resilience with
a1_surface_bridge.a1_call_surface WITHOUT modifying executor_harness.py.

Usage:
    import tools.a1_activate as _  # side-effect: patches harness
    from tools.executor_harness import ExecutorStateMachine, run_calibration_family
    # All subsequent calls to the harness now route through the bridge.

The substitution is explicit and testable:
    from tools import executor_harness
    assert executor_harness.call_model_api_with_resilience is a1_activate.ORIGINAL_FN
      => before activation
    import tools.a1_activate
    assert executor_harness.call_model_api_with_resilience is NOT a1_activate.ORIGINAL_FN
      => after activation

Part of representation-lifting-s1 Amendment A1.
"""

import os
import functools
from typing import Optional

import tools.executor_harness as _harness
from tools.a1_surface_bridge import a1_call_surface, _load_a1_config

# ---------------------------------------------------------------------------
# Preserve the original function for test assertions
# ---------------------------------------------------------------------------
ORIGINAL_FN = _harness.call_model_api_with_resilience

# ---------------------------------------------------------------------------
# Turn counter — maintained across calls within one ExecutorStateMachine run
# ---------------------------------------------------------------------------
_turn_counter: dict = {}  # keyed by (model_id, artifact_dir) for multi-run safety


def _get_and_increment_turn(key: str) -> int:
    current = _turn_counter.get(key, 0)
    _turn_counter[key] = current + 1
    return current


def reset_turn_counter(key: Optional[str] = None) -> None:
    """Reset turn counter. If key is None, clear all. Called between runs."""
    if key is None:
        _turn_counter.clear()
    else:
        _turn_counter.pop(key, None)


# ---------------------------------------------------------------------------
# Load A1 config once at import time
# ---------------------------------------------------------------------------
_A1_CONFIG: Optional[dict] = None
_A1_CONFIG_PATH: Optional[str] = None
_ARTIFACT_DIR: Optional[str] = None


def configure(
    a1_config_path: Optional[str] = None,
    artifact_dir: Optional[str] = None,
) -> None:
    """
    Optionally set a custom a1_config_path and artifact_dir before activation.
    If not called, defaults are used (evidence/amendment_a1/a1_transport_config.json).
    """
    global _A1_CONFIG_PATH, _ARTIFACT_DIR, _A1_CONFIG
    _A1_CONFIG_PATH = a1_config_path
    _ARTIFACT_DIR = artifact_dir
    _A1_CONFIG = _load_a1_config(a1_config_path)


def _build_patched_fn():
    """Return the patched call_model_api_with_resilience function."""

    @functools.wraps(ORIGINAL_FN)
    def _patched(model_id, messages, system_prompt, remaining_wallclock, config, transcript):
        global _A1_CONFIG, _A1_CONFIG_PATH, _ARTIFACT_DIR
        if _A1_CONFIG is None:
            _A1_CONFIG = _load_a1_config(_A1_CONFIG_PATH)

        art_dir = _ARTIFACT_DIR
        if art_dir is None:
            root = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..")
            )
            art_dir = os.path.join(root, "evidence", "amendment_a1", "run_artifacts")

        turn_key = f"{model_id}::{art_dir}"
        turn_number = _get_and_increment_turn(turn_key)

        return a1_call_surface(
            model_id=model_id,
            messages=messages,
            system_prompt=system_prompt,
            remaining_wallclock=remaining_wallclock,
            config=config,
            transcript=transcript,
            a1_config=_A1_CONFIG,
            artifact_dir=art_dir,
            turn_number=turn_number,
        )

    return _patched


# ---------------------------------------------------------------------------
# Apply the patch at import time
# ---------------------------------------------------------------------------
_PATCHED_FN = _build_patched_fn()
_harness.call_model_api_with_resilience = _PATCHED_FN

# Confirm the patch is live
assert _harness.call_model_api_with_resilience is _PATCHED_FN, \
    "A1 activation failed: harness was not patched"
assert _harness.call_model_api_with_resilience is not ORIGINAL_FN, \
    "A1 activation failed: original function still in place"
