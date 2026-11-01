"""Sandboxed repository shallow cloning and safe tree materialization (RULES B1, B5 & ARCHITECTURE 7)."""

import os
import re
import shutil
from typing import Any, Dict, List, Optional, Set

from backend.app.config import get_settings
from backend.app.core.subprocess_runner import run_tool
from backend.app.errors import AppError

# Directories to strictly exclude from materialization
IGNORED_DIRS = {
    "node_modules", "vendor", "dist", "build", ".git", "venv",
    ".venv", "__pycache__", "third_party", ".tox", ".idea", ".vscode"
}

# Windows reserved device names that must never be created on disk
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

# Always preserve dependency manifest files even if slightly larger
MANIFEST_FILENAMES = {
    "requirements.txt", "requirements-dev.txt", "package.json", "package-lock.json",
    "poetry.lock", "pyproject.toml", "pom.xml", "go.mod", "go.sum", "cargo.toml", "cargo.lock"
}


def is_safe_relative_path(path: str, base_dir: str) -> bool:
    """Ensure path is relative, contains no path traversal (..), and resolves strictly inside base_dir."""
    if not path or "\0" in path:
        return False

    # Check for drive letter or leading root slashes
    if re.match(r"^[A-Za-z]:", path) or path.startswith(("/", "\\")):
        return False

    parts = re.split(r"[/\\]+", path)
    for part in parts:
        if part in ("..", ""):
            return False
        # Strip extension for reserved check (e.g. aux.txt is invalid on Windows)
        base_part = part.split(".")[0].upper()
        if base_part in WINDOWS_RESERVED_NAMES:
            return False

    # Ensure resolved path remains strictly within base_dir
    resolved_base = os.path.abspath(base_dir)
    resolved_target = os.path.abspath(os.path.join(base_dir, path))
    return resolved_target.startswith(resolved_base + os.sep)


def create_work_dir(analysis_id: int) -> str:
    """Create isolated scratch work directory for an analysis."""
    settings = get_settings()
    work_dir = os.path.abspath(os.path.join(settings.DATA_DIR, "work", str(analysis_id)))
    os.makedirs(work_dir, exist_ok=True)
    return work_dir


def cleanup_work_dir(work_dir: str) -> None:
    """Guarantee safe deletion of analysis work directory in finally blocks (RULES B12)."""
    if not work_dir:
        return
    abs_dir = os.path.abspath(work_dir)
    if os.path.exists(abs_dir):
        def remove_readonly(func, path, _):
            try:
                os.chmod(path, 0o777)
                func(path)
            except Exception:
                pass

        try:
            shutil.rmtree(abs_dir, onerror=remove_readonly)
        except Exception:
            pass


def clone_bare_repo(repo_name: str, target_git_dir: str, months: int = 12, token: Optional[str] = None) -> None:
    """Execute a bare shallow clone into target_git_dir without a working tree or hook execution."""
    target_git_dir = os.path.abspath(target_git_dir)
    if os.path.exists(target_git_dir):
        cleanup_work_dir(target_git_dir)

    repo_url = f"https://github.com/{repo_name}.git"

    argv = [
        "git", "clone", "--bare", "--single-branch", "--no-tags",
        "--filter=blob:none", "--depth=100", "--no-recurse-submodules",
        repo_url, target_git_dir,
    ]

    extra_env: Dict[str, str] = {}
    if token:
        # Pass token securely via Basic Auth in GIT_CONFIG headers (GitHub Git HTTP expects Basic Auth)
        import base64
        auth_str = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("utf-8")
        extra_env["GIT_CONFIG_COUNT"] = "1"
        extra_env["GIT_CONFIG_KEY_0"] = "http.extraheader"
        extra_env["GIT_CONFIG_VALUE_0"] = f"AUTHORIZATION: Basic {auth_str}"

    parent_dir = os.path.dirname(target_git_dir)
    os.makedirs(parent_dir, exist_ok=True)

    result = run_tool(argv, timeout=180.0, cwd=parent_dir, env=extra_env)
    if result.returncode != 0:
        # Fallback to standard clone without blob filter
        argv_fallback = [
            "git", "clone", "--bare", "--single-branch", "--no-tags",
            "--depth=100", "--no-recurse-submodules",
            repo_url, target_git_dir,
        ]
        result = run_tool(argv_fallback, timeout=180.0, cwd=parent_dir, env=extra_env)
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace")
        raise AppError("STAGE_FAILED", f"Git clone failed: {err}", status_code=500)


def materialize_tree(
    git_dir: str,
    target_src_dir: str,
    head_sha: str,
    max_files: int = 3000,
    max_file_kb: int = 500,
) -> Dict[str, Any]:
    """Parse git tree, filter unsafe entries, and extract safe source files (ARCHITECTURE 7)."""
    os.makedirs(target_src_dir, exist_ok=True)

    # 1. List tree entries with sizes and modes
    ls_result = run_tool(
        ["git", "ls-tree", "-r", "-z", "-l", head_sha],
        timeout=60.0,
        cwd=git_dir,
    )
    if ls_result.returncode != 0:
        # Fallback to HEAD if head_sha is not present in shallow clone
        ls_result = run_tool(
            ["git", "ls-tree", "-r", "-z", "-l", "HEAD"],
            timeout=60.0,
            cwd=git_dir,
        )
    if ls_result.returncode != 0:
        err = ls_result.stderr.decode("utf-8", errors="replace").strip()
        raise AppError("STAGE_FAILED", f"Failed to list git repository tree: {err or 'unknown error'}", status_code=500)

    # Output format per entry: "<mode> <type> <object> <size>\t<path>\0"
    raw_entries = ls_result.stdout.split(b"\0")
    materialized_count = 0
    truncated = False
    seen_paths_lower: Set[str] = set()
    materialized_paths: List[str] = []

    for entry in raw_entries:
        if not entry:
            continue
        try:
            meta, path_bytes = entry.split(b"\t", 1)
            path_str = path_bytes.decode("utf-8", errors="replace")
            meta_parts = meta.decode("ascii", errors="replace").split()
            mode = meta_parts[0]
            obj_type = meta_parts[1]
            obj_sha = meta_parts[2]
            size_str = meta_parts[3] if len(meta_parts) > 3 else "0"
            size_bytes = int(size_str) if size_str.isdigit() else 0
        except Exception:
            continue

        # Skip non-blobs, symlinks (120000), and submodules (160000) (ARCHITECTURE 7)
        if obj_type != "blob" or mode in ("120000", "160000"):
            continue

        # Check path safety against path traversal and Windows reserved names
        if not is_safe_relative_path(path_str, target_src_dir):
            continue

        # Check for ignored directories
        path_segments = set(re.split(r"[/\\]+", path_str))
        if path_segments.intersection(IGNORED_DIRS):
            continue

        # Check file extension / minification
        base_name = os.path.basename(path_str).lower()
        if base_name.endswith((".min.js", ".min.css", ".map", ".lockb")):
            continue

        # Check file size limit unless it's a known dependency manifest
        if base_name not in MANIFEST_FILENAMES and size_bytes > (max_file_kb * 1024):
            continue

        # Case-insensitive collision detection
        lower_path = path_str.lower()
        if lower_path in seen_paths_lower:
            continue
        seen_paths_lower.add(lower_path)

        # File count cap
        if materialized_count >= max_files:
            truncated = True
            break

        # Read content via git cat-file
        cat_result = run_tool(["git", "cat-file", "-p", obj_sha], timeout=15.0, cwd=git_dir)
        if cat_result.returncode != 0:
            continue

        content_bytes = cat_result.stdout

        # Binary check: skip if NUL byte in first 8 KB (unless manifest)
        if base_name not in MANIFEST_FILENAMES and b"\0" in content_bytes[:8192]:
            continue

        # Write to safe path on disk
        dest_path = os.path.join(target_src_dir, path_str)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(content_bytes)

        materialized_count += 1
        materialized_paths.append(path_str)

    return {
        "materialized_count": materialized_count,
        "truncated": truncated,
        "paths": materialized_paths,
    }
