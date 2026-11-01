"""Secret scanner with regex detection, Shannon entropy verification, and strict 4-char masking (RULES B7)."""

import math
import re
from pathlib import Path
from typing import Any, Dict, List

# Obvious placeholder substrings to ignore
PLACEHOLDER_SUBSTRINGS = {
    "your_key", "your_token", "your_secret", "my_secret", "example_key",
    "placeholder", "dummy_token", "dummy_key", "test_key", "fake_key",
    "change_me", "insert_here",
}

# Regex patterns for well-known API keys and credentials
KNOWN_SECRET_PATTERNS = [
    ("github_token", re.compile(r"\b(ghp_[A-Za-z0-9_]{36,255}|github_pat_[A-Za-z0-9_]{22,255})\b")),
    ("aws_access_key", re.compile(r"\b(AKIA[0-9A-Z]{16})\b")),
    ("slack_token", re.compile(r"\b(xox[baprs]-[0-9A-Za-z-]{10,48})\b")),
    ("private_key", re.compile(r"-----BEGIN\s+[A-Z\s]+PRIVATE\s+KEY-----")),
    ("generic_secret", re.compile(r"""(?:api[_-]?key|auth[_-]?token|secret|password|access[_-]?token)\s*[:=]\s*['"]([A-Za-z0-9_\-+/]{16,})['"]""", re.IGNORECASE)),
]


def shannon_entropy(data: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not data:
        return 0.0
    entropy = 0.0
    length = len(data)
    freq = {}
    for char in data:
        freq[char] = freq.get(char, 0) + 1
    for count in freq.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


def is_placeholder(val: str) -> bool:
    """Check if the string matches common developer placeholders."""
    lower = val.lower()
    for placeholder in PLACEHOLDER_SUBSTRINGS:
        if placeholder in lower:
            return True
    return False


def mask_secret(secret: str) -> str:
    """Return strictly at most first 4 characters followed by '****' (RULES B7)."""
    if not secret:
        return "****"
    prefix = secret[:4]
    return f"{prefix}****"


def scan_file_for_secrets(rel_path: str, content: str) -> List[Dict[str, Any]]:
    """Scan content of a single file for exposed secrets."""
    findings: List[Dict[str, Any]] = []
    lines = content.splitlines()

    for line_idx, line in enumerate(lines, start=1):
        # Ignore comments or empty lines if desired, but secrets can exist in comments
        for pattern_name, regex in KNOWN_SECRET_PATTERNS:
            for match in regex.finditer(line):
                matched_val = match.group(1) if match.groups() else match.group(0)

                # Skip obvious placeholders
                if is_placeholder(matched_val):
                    continue

                # For generic secrets, enforce Shannon entropy >= 3.2 to reject low-randomness words
                if pattern_name == "generic_secret":
                    if shannon_entropy(matched_val) < 3.2:
                        continue

                masked = mask_secret(matched_val)
                findings.append({
                    "file": rel_path,
                    "line": line_idx,
                    "type": pattern_name,
                    "masked": masked,
                    "severity": "HIGH",
                })

    return findings


def scan_repository_secrets(source_dir: Path, source_files: List[str]) -> Dict[str, Any]:
    """Scan all materialized source files for secrets."""
    all_findings: List[Dict[str, Any]] = []

    for rel_path in source_files:
        full_path = source_dir / rel_path
        if not full_path.is_file():
            continue

        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        findings = scan_file_for_secrets(rel_path, content)
        all_findings.extend(findings)

    return {
        "total_secrets": len(all_findings),
        "findings": all_findings,
    }
