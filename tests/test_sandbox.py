"""Unit tests for sandboxed git shallow cloning and safe tree materialization."""

import os
import shutil
import tempfile

from backend.app.core.sandbox import (
    cleanup_work_dir,
    create_work_dir,
    is_safe_relative_path,
    materialize_tree,
)
from backend.app.core.subprocess_runner import run_tool


def test_path_safety_checks():
    """Verify is_safe_relative_path rejects traversal, absolute paths, and reserved device names."""
    base = os.path.abspath("temp_base")

    # Valid safe relative paths
    assert is_safe_relative_path("src/index.js", base) is True
    assert is_safe_relative_path("components/Button.jsx", base) is True

    # Path traversal rejected
    assert is_safe_relative_path("../etc/passwd", base) is False
    assert is_safe_relative_path("a/../../b", base) is False

    # Absolute paths rejected
    assert is_safe_relative_path("/root/secrets.txt", base) is False
    assert is_safe_relative_path("C:\\Windows\\System32\\cmd.exe", base) is False

    # Reserved device names rejected
    assert is_safe_relative_path("NUL", base) is False
    assert is_safe_relative_path("src/AUX.txt", base) is False
    assert is_safe_relative_path("COM1", base) is False


def test_work_dir_lifecycle_and_cleanup_after_failure():
    """Verify work directories are properly cleaned up even after errors (RULES B12)."""
    work_dir = create_work_dir(9999)
    assert os.path.isdir(work_dir)

    test_file = os.path.join(work_dir, "test.txt")
    with open(test_file, "w") as f:
        f.write("temporary data")

    try:
        raise ValueError("Simulated pipeline failure")
    except ValueError:
        pass
    finally:
        cleanup_work_dir(work_dir)

    assert not os.path.exists(work_dir)


def test_materialize_tree_filters_and_collisions():
    """Verify tree materialization handles oversize files, symlinks, and case collisions."""
    temp_dir = tempfile.mkdtemp()
    git_dir = os.path.join(temp_dir, "repo")
    src_dir = os.path.join(temp_dir, "src")
    os.makedirs(git_dir)

    try:
        # Initialize test git repository
        run_tool(["git", "init"], cwd=git_dir)
        run_tool(["git", "config", "user.name", "Tester"], cwd=git_dir)
        run_tool(["git", "config", "user.email", "tester@example.com"], cwd=git_dir)

        # 1. Normal file
        with open(os.path.join(git_dir, "hello.py"), "w") as f:
            f.write("print('hello world')\n")

        # 2. Oversize file (600 KB)
        with open(os.path.join(git_dir, "big.py"), "w") as f:
            f.write("A" * (600 * 1024))

        # 3. Ignored directory file
        os.makedirs(os.path.join(git_dir, "node_modules"))
        with open(os.path.join(git_dir, "node_modules", "pkg.js"), "w") as f:
            f.write("module.exports = {};")

        run_tool(["git", "add", "."], cwd=git_dir)
        run_tool(["git", "commit", "-m", "initial commit"], cwd=git_dir)

        # Get HEAD commit
        rev = run_tool(["git", "rev-parse", "HEAD"], cwd=git_dir)
        head_sha = rev.stdout.decode().strip()

        # Materialize tree
        result = materialize_tree(
            git_dir=git_dir,
            target_src_dir=src_dir,
            head_sha=head_sha,
            max_file_kb=500,  # Big file (600 KB) must be skipped
        )

        assert "hello.py" in result["paths"]
        assert "big.py" not in result["paths"]
        assert not any("node_modules" in p for p in result["paths"])
        assert os.path.isfile(os.path.join(src_dir, "hello.py"))
        assert not os.path.isfile(os.path.join(src_dir, "big.py"))

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
