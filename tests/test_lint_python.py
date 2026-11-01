"""Tests for Python linting with Pylint and Bandit and hostile pylintrc defense."""

from pathlib import Path

from backend.app.analyzers.lint_python import (
    analyze_python_lint,
    run_bandit_analysis,
    run_pylint_analysis,
)


def test_hostile_pylintrc_defense(tmp_path: Path):
    """Verify that a repo with a hostile .pylintrc init-hook cannot execute arbitrary Python."""
    marker_file = tmp_path / "hostile_marker.txt"

    # Hostile .pylintrc that tries to create a file via init-hook
    hostile_rc = tmp_path / ".pylintrc"
    escaped_marker = str(marker_file).replace("\\", "\\\\")
    hostile_rc.write_text(
        f'[MASTER]\ninit-hook="import os; open(\'{escaped_marker}\', \'w\').write(\'pwned\')"\n',
        encoding="utf-8",
    )

    # Simple python file
    py_file = tmp_path / "hello.py"
    py_file.write_text("print('hello world')\n", encoding="utf-8")

    # Run pylint analysis on the repo
    res = run_pylint_analysis(tmp_path, ["hello.py"])

    # ASSERTION: The marker file must NOT exist!
    assert not marker_file.exists(), "CRITICAL: Hostile pylintrc init-hook was executed!"
    assert "messages" in res


def test_bandit_finds_issue(tmp_path: Path):
    """Verify Bandit analyzes python files and reports known findings."""
    py_file = tmp_path / "vuln.py"
    # assert used is checked in our default profile
    py_file.write_text("assert True, 'assertion used'\n", encoding="utf-8")

    res = run_bandit_analysis(tmp_path, ["vuln.py"])
    assert res["sampled_files_count"] == 1
    assert "findings" in res


def test_unified_python_lint(tmp_path: Path):
    """Verify analyze_python_lint aggregates both tools."""
    py_file = tmp_path / "clean.py"
    py_file.write_text("x = 1\ny = 2\nz = x + y\n", encoding="utf-8")

    res = analyze_python_lint(tmp_path, ["clean.py"])
    assert "pylint" in res
    assert "bandit" in res
    assert isinstance(res["total_issues"], int)
