#!/usr/bin/env python3
r"""
tools/nontriviality_filter.py
Authoritative Gate 1 / Gate 2 Adjudicator and Filter Module.
Part of the representation-lifting-s1 experimental protocol (v0.20).

Tri-state fail-closed adjudicator contract:
  0 = NONTRIVIAL (canonical baseline elaborates with sorry; all 4 tactics fail to prove)
  1 = TRIVIAL (proved by at least one basic tactic: rfl, decide, linarith, ring)
  2 = INPUT_ERROR / BASELINE_INVALID (fails baseline elaboration with sorry, syntax error,
      unstripped sorry, missing file, or infrastructure hang)

Mechanical Transformations for Canonical Statement Elaboration:
  1. Extract canonical statement (strip comments / trailing proof placeholder).
  2. Hoist imports to file header.
  3. Prepend 'import Mathlib' if missing.
  4. Append ':= by sorry' (baseline) or ':= by <tactic>' (tactic probes).
  5. Elaborate under deterministic 'set_option maxHeartbeats 200000'.
"""

import sys
import os
import re
import uuid
import shutil
import atexit
import subprocess
from typing import Callable

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

MAX_HEARTBEATS = 200000
WATCHDOG_TIMEOUT_SECONDS = 600
BASIC_TACTICS = ("rfl", "decide", "linarith", "ring")

_CACHED_LEAN_PATH: str | None = None
_BUILD_DIR = os.path.join(PROJECT_ROOT, f".lake_gate1_build_{os.getpid()}")

def _cleanup_build_dir():
    if os.path.exists(_BUILD_DIR):
        shutil.rmtree(_BUILD_DIR, ignore_errors=True)

atexit.register(_cleanup_build_dir)

def summarize_lean_error(stderr_text: str) -> str:
    """Extracts first meaningful error line from Lean stderr output."""
    lines = [line.strip() for line in stderr_text.splitlines() if line.strip()]
    for line in lines:
        if "error:" in line or "timeout" in line or "unknown identifier" in line:
            cleaned = re.sub(r"^[^:]+:\d+:\d+:\s*", "", line)
            return cleaned[:160]
    return lines[0][:160] if lines else "unknown_elaboration_error"

def get_project_lean_env(project_root: str = PROJECT_ROOT) -> dict[str, str]:
    """Prepares sanitized environment with elan in PATH and cached LEAN_PATH."""
    global _CACHED_LEAN_PATH
    env = os.environ.copy()
    for k in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GITHUB_TOKEN", "SSH_AUTH_SOCK"]:
        env.pop(k, None)

    home = os.path.expanduser("~")
    elan_bin = os.path.join(home, ".elan", "bin")
    if elan_bin not in env.get("PATH", ""):
        env["PATH"] = f"{elan_bin}:{env.get('PATH', '')}"

    if _CACHED_LEAN_PATH is None:
        lp_proc = subprocess.run(
            ["lake", "env", "printenv", "LEAN_PATH"],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        _CACHED_LEAN_PATH = lp_proc.stdout.strip()

    os.makedirs(_BUILD_DIR, exist_ok=True)
    env["LEAN_PATH"] = f"{_BUILD_DIR}:{_CACHED_LEAN_PATH}"
    return env

def default_lean_runner(
    code: str,
    project_root: str = PROJECT_ROOT,
    watchdog_seconds: int = WATCHDOG_TIMEOUT_SECONDS
) -> tuple[int, str, str, bool]:
    """
    Executes a Lean snippet via `lake env lean` within a project-local temporary build directory.
    Guarantees full compatibility with Mathlib dependencies on CI runners.
    Returns: (returncode, stdout, stderr, is_watchdog_timeout)
    """
    env = get_project_lean_env(project_root)
    file_id = uuid.uuid4().hex[:12]
    temp_lean = os.path.join(_BUILD_DIR, f"candidate_{file_id}.lean")
    with open(temp_lean, "w", encoding="utf-8") as f:
        f.write(code)

    try:
        proc = subprocess.run(
            ["lake", "env", "lean", temp_lean],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=watchdog_seconds
        )
        return proc.returncode, proc.stdout, proc.stderr, False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return -1, stdout, stderr, True
    finally:
        if os.path.exists(temp_lean):
            try:
                os.remove(temp_lean)
            except OSError:
                pass

def build_wrapped_lean_code(
    stripped_decl: str,
    proof_tactic: str,
    max_heartbeats: int = MAX_HEARTBEATS
) -> str:
    """
    Performs canonical statement transformations:
    - Hoists import statements to top
    - Prepends 'import Mathlib' if absent
    - Sets deterministic maxHeartbeats option
    - Appends ':= by <proof_tactic>'
    """
    import_lines = []
    decl_lines = []
    for line in stripped_decl.splitlines():
        if re.match(r"^\s*import\b", line):
            cleaned = re.sub(r"^\s*", "", line).strip()
            if cleaned not in import_lines:
                import_lines.append(cleaned)
        else:
            decl_lines.append(line)

    if "import Mathlib" not in import_lines:
        import_lines.insert(0, "import Mathlib")

    imports_header = "\n".join(import_lines)
    decl_body = "\n".join(decl_lines).strip()

    return (
        f"{imports_header}\n\n"
        f"set_option maxHeartbeats {max_heartbeats}\n\n"
        f"{decl_body} := by\n"
        f"  {proof_tactic}\n"
    )

def evaluate_statement(
    stripped_decl: str,
    project_root: str = PROJECT_ROOT,
    max_heartbeats: int = MAX_HEARTBEATS,
    watchdog_seconds: int = WATCHDOG_TIMEOUT_SECONDS,
    lean_runner: Callable[[str, str, int], tuple[int, str, str, bool]] = default_lean_runner
) -> tuple[str, str]:
    """
    Evaluates an extracted canonical declaration snippet through Gate 2 & Gate 1.
    Authoritative implementation shared by tools/nontriviality_filter and tools/build_pool.
    Returns: (status, reason)
      status in {"POOL", "EXCLUDED_TRIVIAL", "EXCLUDED_TOOLCHAIN_INCOMPATIBLE", "INFRA_HANG"}
    """
    # 1. Gate 2: Canonical statement baseline elaboration with sorry
    baseline_code = build_wrapped_lean_code(stripped_decl, "sorry", max_heartbeats)
    rc, stdout, stderr, is_hang = lean_runner(baseline_code, project_root, watchdog_seconds)

    if is_hang:
        return "INFRA_HANG", f"watchdog_timeout_on_baseline (>{watchdog_seconds}s)"

    if rc != 0:
        if "(deterministic) timeout" in stderr or "(deterministic) timeout" in stdout:
            return "EXCLUDED_TOOLCHAIN_INCOMPATIBLE", "deterministic_heartbeat_timeout_on_baseline"
        err_msg = summarize_lean_error(stderr or stdout)
        return "EXCLUDED_TOOLCHAIN_INCOMPATIBLE", f"baseline_elaboration_failed: {err_msg}"

    # 2. Gate 1: Probe the 4 basic tactics under maxHeartbeats
    for tac in BASIC_TACTICS:
        tac_code = build_wrapped_lean_code(stripped_decl, tac, max_heartbeats)
        rc, stdout, stderr, is_hang = lean_runner(tac_code, project_root, watchdog_seconds)

        if is_hang:
            return "INFRA_HANG", f"watchdog_timeout_on_{tac} (>{watchdog_seconds}s)"

        if rc == 0:
            return "EXCLUDED_TRIVIAL", f"solved_by_{tac}"

    return "POOL", "passed_all_tactics"

def evaluate_file(
    filepath: str,
    project_root: str = PROJECT_ROOT,
    max_heartbeats: int = MAX_HEARTBEATS,
    watchdog_seconds: int = WATCHDOG_TIMEOUT_SECONDS,
    lean_runner: Callable[[str, str, int], tuple[int, str, str, bool]] = default_lean_runner
) -> tuple[int, str, str]:
    """
    Evaluates a single file snippet against the tri-state filter contract.
    Returns: (returncode, stdout_msg, stderr_msg)
      0 = NONTRIVIAL
      1 = TRIVIAL
      2 = INPUT_ERROR / BASELINE_INVALID
    """
    if not os.path.isfile(filepath):
        return 2, "", f"INPUT_ERROR: Target file '{filepath}' does not exist."

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Fail-closed check: Target file must not contain unstripped sorry
    if re.search(r'(^|[^a-zA-Z0-9_`])sorry([^a-zA-Z0-9_`]|$)', content):
        return 2, "", "INPUT_ERROR / BASELINE_INVALID: Target snippet contains unstripped 'sorry'."

    status, reason = evaluate_statement(
        content,
        project_root=project_root,
        max_heartbeats=max_heartbeats,
        watchdog_seconds=watchdog_seconds,
        lean_runner=lean_runner
    )

    if status == "POOL":
        return 0, "NONTRIVIAL: Passed all 4 basic tactic tests.", ""
    elif status == "EXCLUDED_TRIVIAL":
        tac = reason.replace("solved_by_", "")
        return 1, f"TRIVIAL: Solved by tactic '{tac}'", ""
    elif status == "EXCLUDED_TOOLCHAIN_INCOMPATIBLE":
        return 2, "", f"INPUT_ERROR / BASELINE_INVALID: Statement failed baseline elaboration with sorry. ({reason})"
    elif status == "INFRA_HANG":
        return 2, "", f"INPUT_ERROR / BASELINE_INVALID: Infrastructure watchdog hang. ({reason})"
    else:
        return 2, "", f"INPUT_ERROR / BASELINE_INVALID: Unrecognized status {status} ({reason})"

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <lean_file_or_declaration_snippet>", file=sys.stderr)
        sys.exit(2)

    target_file = sys.argv[1]
    rc, stdout_msg, stderr_msg = evaluate_file(target_file)
    if stdout_msg:
        print(stdout_msg)
    if stderr_msg:
        print(stderr_msg, file=sys.stderr)
    sys.exit(rc)

if __name__ == "__main__":
    main()
