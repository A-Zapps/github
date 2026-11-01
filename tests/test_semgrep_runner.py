"""Tests for Semgrep runner and custom rules configuration."""

from pathlib import Path

import yaml

from backend.app.analyzers.semgrep_runner import SEMGREP_RULES_DIR, run_semgrep_analysis


def test_semgrep_rules_file_valid():
    """Verify rules.yaml in semgrep_rules is valid YAML with all expected rule ids."""
    rules_file = SEMGREP_RULES_DIR / "rules.yaml"
    assert rules_file.is_file()

    content = yaml.safe_load(rules_file.read_text(encoding="utf-8"))
    assert "rules" in content
    rule_ids = {r["id"] for r in content["rules"]}
    assert "python-sql-string-building" in rule_ids
    assert "javascript-inner-html" in rule_ids
    assert "python-eval-exec" in rule_ids
    assert "python-subprocess-shell-true" in rule_ids
    assert "python-unsafe-deserialization" in rule_ids
    assert "python-weak-hash" in rule_ids


def test_semgrep_disabled_reports_skipped(tmp_path: Path):
    """Verify that when Semgrep is disabled, it returns status 'skipped' and reason 'disabled'."""
    res = run_semgrep_analysis(tmp_path, enabled_override=False)
    assert res["status"] == "skipped"
    assert res["reason"] == "disabled"
    assert res["findings"] == []
    assert res["total"] == 0


def test_semgrep_missing_executable_skips_gracefully(tmp_path: Path):
    """Verify that if enabled but binary is missing, it skips without raising an exception."""
    res = run_semgrep_analysis(tmp_path, enabled_override=True)
    assert res["status"] in ("skipped", "completed")
    if res["status"] == "skipped":
        assert res["reason"] in ("disabled", "semgrep_not_installed")
