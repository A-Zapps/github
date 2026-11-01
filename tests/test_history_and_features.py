"""Tests for history analysis and as-of cutoff date feature invariance (RULES D2)."""

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from backend.app.analyzers.history import (
    compute_file_history_features,
    compute_repo_history_features,
    is_bugfix_message,
    parse_git_log_history,
)


def _run_git(args, cwd):
    git_cmd = r"C:\Program Files\Git\cmd\git.exe" if os.name == "nt" else "git"
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "Test Author"
    env["GIT_AUTHOR_EMAIL"] = "test@example.com"
    env["GIT_COMMITTER_NAME"] = "Test Author"
    env["GIT_COMMITTER_EMAIL"] = "test@example.com"
    subprocess.run([git_cmd] + args, cwd=cwd, env=env, check=True, capture_output=True)


def _commit_at(repo_dir: Path, filename: str, content: str, message: str, date_iso: str):
    f = repo_dir / filename
    f.write_text(content, encoding="utf-8")
    _run_git(["add", filename], str(repo_dir))

    git_cmd = r"C:\Program Files\Git\cmd\git.exe" if os.name == "nt" else "git"
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "Test Author"
    env["GIT_AUTHOR_EMAIL"] = "test@example.com"
    env["GIT_COMMITTER_NAME"] = "Test Author"
    env["GIT_COMMITTER_EMAIL"] = "test@example.com"
    env["GIT_AUTHOR_DATE"] = date_iso
    env["GIT_COMMITTER_DATE"] = date_iso
    subprocess.run([git_cmd, "commit", "-m", message], cwd=str(repo_dir), env=env, check=True, capture_output=True)


def test_bugfix_pattern_matching():
    """Verify bugfix message identification and exclusion of typos/docs."""
    assert is_bugfix_message("fix: resolve null pointer exception in worker")
    assert is_bugfix_message("Fix bug in calculation")
    assert is_bugfix_message("security patch for CVE-2023-1234")
    assert is_bugfix_message("prevent crash on empty list")

    # Excluded patterns
    assert not is_bugfix_message("fix typo in documentation")
    assert not is_bugfix_message("fix readme docs")
    assert not is_bugfix_message("ci: fix github action syntax")
    assert not is_bugfix_message("initial commit")


def test_as_of_invariance(tmp_path: Path):
    """CRITICAL: Adding commits after cutoff_date must NOT change features as of cutoff_date."""
    repo_dir = tmp_path / "invariance_repo"
    repo_dir.mkdir()

    _run_git(["init"], str(repo_dir))
    _run_git(["config", "user.name", "Test User"], str(repo_dir))
    _run_git(["config", "user.email", "test@example.com"], str(repo_dir))

    # Cutoff date T: 2025-06-01T00:00:00Z
    cutoff_date = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)

    # 1. Commit before cutoff (2025-04-15)
    _commit_at(
        repo_dir,
        "worker.py",
        "def work(): return 1\n",
        "feat: add worker process",
        "2025-04-15T12:00:00Z",
    )

    # 2. Bugfix commit before cutoff (2025-05-10)
    _commit_at(
        repo_dir,
        "worker.py",
        "def work(): return 2\n",
        "fix: resolve crash in worker return",
        "2025-05-10T12:00:00Z",
    )

    # Compute features as of cutoff date T (BEFORE future commits exist)
    hist_1 = parse_git_log_history(str(repo_dir), cutoff_date=cutoff_date)
    file_feats_1 = compute_file_history_features(hist_1, cutoff_date)
    repo_feats_1 = compute_repo_history_features(hist_1, cutoff_date)

    assert "worker.py" in file_feats_1
    assert file_feats_1["worker.py"]["commits_12m"] == 2
    assert file_feats_1["worker.py"]["bugfix_commits_12m"] == 1
    assert repo_feats_1["distinct_authors"] == 1

    # 3. Now add commits in the FUTURE after cutoff (2025-07-20 and 2025-08-15)
    _commit_at(
        repo_dir,
        "worker.py",
        "def work(): return 3\ndef extra(): pass\n",
        "feat: huge future refactoring",
        "2025-07-20T12:00:00Z",
    )
    _commit_at(
        repo_dir,
        "future_file.py",
        "print('future')\n",
        "feat: brand new future module",
        "2025-08-15T12:00:00Z",
    )

    # Re-compute features as of cutoff date T (AFTER future commits exist)
    hist_2 = parse_git_log_history(str(repo_dir), cutoff_date=cutoff_date)
    file_feats_2 = compute_file_history_features(hist_2, cutoff_date)
    repo_feats_2 = compute_repo_history_features(hist_2, cutoff_date)

    # AS-OF INVARIANCE ASSERTION:
    # Future commits must have ZERO effect on features as of cutoff date!
    assert "future_file.py" not in file_feats_2, "Future file leaked into past features!"
    assert file_feats_1 == file_feats_2, "File features as of cutoff changed after adding future commits!"
    assert repo_feats_1 == repo_feats_2, "Repo features as of cutoff changed after adding future commits!"
