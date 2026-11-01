#!/usr/bin/env python3
"""Scanner for forbidden patterns in production code (RULES A2 & ARCHITECTURE 17).

Ensures that random generators, mock data generators, lorem ipsum, and
fabricated numbers never enter backend/app or frontend.
"""

import os
import re
import sys

# Directory targets to check
TARGET_DIRS = ["backend/app", "frontend/js"]

# Forbidden regex patterns
FORBIDDEN_PATTERNS = [
    (re.compile(r"\bimport\s+random\b"), "Forbidden 'import random' found"),
    (re.compile(r"\bfrom\s+random\s+import\b"), "Forbidden 'from random import' found"),
    (re.compile(r"\bnp\.random\b"), "Forbidden 'np.random' found"),
    (re.compile(r"\bnumpy\.random\b"), "Forbidden 'numpy.random' found"),
    (re.compile(r"\bfaker\b", re.IGNORECASE), "Forbidden 'faker' reference found"),
    (re.compile(r"\blorem\s+ipsum\b", re.IGNORECASE), "Forbidden 'Lorem Ipsum' placeholder found"),
]


def scan_file(filepath: str) -> list[str]:
    """Scan a single file for forbidden patterns."""
    violations = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, start=1):
                for pattern, desc in FORBIDDEN_PATTERNS:
                    if pattern.search(line):
                        violations.append(f"{filepath}:{line_no}: {desc} -> {line.strip()}")
    except Exception as e:
        violations.append(f"Failed to read {filepath}: {e}")
    return violations


def main() -> int:
    """Scan all target files and exit non-zero if any forbidden pattern is detected."""
    all_violations = []

    for target in TARGET_DIRS:
        if not os.path.exists(target):
            continue
        for root, _, files in os.walk(target):
            for file in files:
                if file.endswith((".py", ".js", ".html", ".css")):
                    filepath = os.path.join(root, file)
                    violations = scan_file(filepath)
                    all_violations.extend(violations)

    if all_violations:
        print("=" * 60, file=sys.stderr)
        print("FORBIDDEN PATTERNS DETECTED (RULES A2):", file=sys.stderr)
        for v in all_violations:
            print(f"  {v}", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        return 1

    print("scan_forbidden: PASS (No mock, random, or placeholder patterns found)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
