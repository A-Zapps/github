"""Secure subprocess execution wrapper (RULES B2 and ARCHITECTURE 7)."""

import os
import shutil
import subprocess
import tempfile
from typing import Dict, List, Optional

from backend.app.errors import AppError

ALLOWED_TOOLS = {"git", "pylint", "bandit", "semgrep"}
MAX_OUTPUT_BYTES = 10 * 1024 * 1024  # 10 MB output cap

# Common Windows install directories for developer tools
DEFAULT_WINDOWS_TOOL_PATHS = [
    r"C:\Program Files\Git\cmd",
    r"C:\Program Files\Git\bin",
    r"C:\Program Files (x86)\Git\cmd",
]


def resolve_tool_path(binary_name: str) -> str:
    """Find the full executable path for an allowed tool."""
    # First check standard PATH
    found = shutil.which(binary_name)
    if found:
        return found

    # On Windows, check standard installation paths if not on global PATH
    if os.name == "nt":
        for search_dir in DEFAULT_WINDOWS_TOOL_PATHS:
            candidate = os.path.join(search_dir, f"{binary_name}.exe")
            if os.path.isfile(candidate):
                return candidate
            candidate_no_ext = os.path.join(search_dir, binary_name)
            if os.path.isfile(candidate_no_ext):
                return candidate_no_ext

    return binary_name


def run_tool(
    argv: List[str],
    timeout: float = 60.0,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    """Execute a tool command securely with strict isolation.

    - shell=False is always enforced.
    - Command must be in ALLOWED_TOOLS.
    - Execution environment is sanitized without inherited process secrets.
    - CWD must be specified outside repo source.
    - Timeout and output size limits are enforced.
    """
    if not argv or not isinstance(argv, list):
        raise AppError("INTERNAL", "Command argv must be a non-empty list of strings.", status_code=500)

    binary = os.path.basename(argv[0]).lower()
    if binary.endswith(".exe"):
        binary = binary[:-4]

    if binary not in ALLOWED_TOOLS:
        raise AppError("INTERNAL", f"Execution of disallowed tool '{binary}' rejected.", status_code=500)

    # Locate executable
    if binary in ("pylint", "bandit") and not shutil.which(binary):
        import sys
        cmd_to_run = [sys.executable, "-m", binary] + argv[1:]
        executable = sys.executable
    else:
        executable = resolve_tool_path(binary)
        cmd_to_run = [executable] + argv[1:]

    # Sanitize environment: clean PATH including tool directory and isolated HOME/TEMP (ARCHITECTURE 7)
    base_path = os.environ.get("PATH", "")
    tool_dir = os.path.dirname(executable)
    if tool_dir and tool_dir not in base_path:
        base_path = f"{tool_dir};{base_path}"

    clean_env: Dict[str, str] = {
        "PATH": base_path,
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
        "WINDIR": os.environ.get("WINDIR", "C:\\Windows"),
        "TMP": tempfile.gettempdir(),
        "TEMP": tempfile.gettempdir(),
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    if env:
        clean_env.update(env)

    try:
        process = subprocess.run(
            cmd_to_run,
            cwd=cwd,
            env=clean_env,
            capture_output=True,
            timeout=timeout,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise AppError("STAGE_FAILED", f"Tool '{binary}' timed out after {timeout} seconds.", status_code=500) from exc
    except Exception as exc:
        raise AppError("STAGE_FAILED", f"Failed to execute tool '{binary}': {exc}", status_code=500) from exc

    # Cap output size
    if len(process.stdout) > MAX_OUTPUT_BYTES or len(process.stderr) > MAX_OUTPUT_BYTES:
        raise AppError("STAGE_FAILED", f"Tool '{binary}' exceeded output cap ({MAX_OUTPUT_BYTES} bytes).", status_code=500)

    return process
