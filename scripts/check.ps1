# Automated Verification Script (Phase 0-10 gate)
$ErrorActionPreference = "Stop"

Write-Host "=== 1/3: Running Ruff Linter ===" -ForegroundColor Cyan
& ".\.venv\Scripts\ruff.exe" check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== 2/3: Running Pytest Test Suite ===" -ForegroundColor Cyan
& ".\.venv\Scripts\pytest.exe" -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== 3/3: Running Forbidden Pattern Scanner ===" -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" scripts/scan_forbidden.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== ALL CHECKS PASSED ===" -ForegroundColor Green
exit 0
