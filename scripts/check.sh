#!/usr/bin/env bash
set -e

echo "=== 1/3: Running Ruff Linter ==="
./.venv/bin/ruff check .

echo "=== 2/3: Running Pytest Test Suite ==="
./.venv/bin/pytest -v

echo "=== 3/3: Running Forbidden Pattern Scanner ==="
./.venv/bin/python scripts/scan_forbidden.py

echo "=== ALL CHECKS PASSED ==="
