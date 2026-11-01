"""Tests for secret scanner with entropy check, placeholder filtering, and masking (RULES B7)."""

from pathlib import Path

from backend.app.analyzers.secrets import (
    mask_secret,
    scan_file_for_secrets,
    scan_repository_secrets,
)


def test_masking_rule():
    """Verify strictly at most 4 characters are exposed followed by '****' (RULES B7)."""
    assert mask_secret("ghp_1234567890abcdef1234567890abcdef123456") == "ghp_****"
    assert mask_secret("AKIAIOSFODNN7EXAMPLE") == "AKIA****"
    assert mask_secret("short") == "shor****"
    assert mask_secret("") == "****"


def test_secret_detection_and_placeholder_skipping(tmp_path: Path):
    """Verify secrets are detected and placeholders are cleanly skipped."""
    file_content = """# Config file
API_KEY = "YOUR_KEY_HERE_12345678" # placeholder, must be skipped
AWS_KEY = "AKIA1234567890ABCDEF" # real pattern, must be caught
GH_TOKEN = "ghp_abcdefghijklmnopqrstuvwxyz1234567890" # real pattern, must be caught
DUMMY = "dummy_token_12345678" # placeholder, must be skipped
"""
    f = tmp_path / "config.py"
    f.write_text(file_content, encoding="utf-8")

    findings = scan_file_for_secrets("config.py", file_content)

    assert len(findings) == 2
    for item in findings:
        # RULES B7: never return more than 4 clear characters
        assert item["masked"].endswith("****")
        assert len(item["masked"]) <= 8

    masked_types = {item["type"] for item in findings}
    assert "aws_access_key" in masked_types
    assert "github_token" in masked_types


def test_repository_secrets_scan(tmp_path: Path):
    """Verify repository scan collects findings across multiple files."""
    f1 = tmp_path / "a.env"
    f1.write_text("GITHUB_TOKEN=ghp_9876543210zyxwvutsrqponmlkjihgfedcba\n", encoding="utf-8")

    f2 = tmp_path / "b.py"
    f2.write_text("print('no secrets here')\n", encoding="utf-8")

    res = scan_repository_secrets(tmp_path, ["a.env", "b.py"])
    assert res["total_secrets"] == 1
    assert res["findings"][0]["file"] == "a.env"
    assert res["findings"][0]["masked"] == "ghp_****"
