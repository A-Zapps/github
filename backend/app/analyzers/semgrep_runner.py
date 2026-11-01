"""Semgrep runner executing curated security rules under ENABLE_SEMGREP flag (RULES B3)."""

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.config import get_settings
from backend.app.core.subprocess_runner import run_tool

SEMGREP_RULES_DIR = Path(__file__).resolve().parent / "semgrep_rules"


def run_semgrep_analysis(
    source_dir: Path,
    enabled_override: Optional[bool] = None,
) -> Dict[str, Any]:
    """Execute Semgrep security analysis using our explicit rule directory.

    If ENABLE_SEMGREP is False, gracefully returns 'skipped: disabled' without failing.
    """
    settings = get_settings()
    is_enabled = settings.ENABLE_SEMGREP if enabled_override is None else enabled_override

    if not is_enabled:
        return {
            "status": "skipped",
            "reason": "disabled",
            "findings": [],
            "total": 0,
        }

    # Check if semgrep executable exists on system
    if not shutil.which("semgrep"):
        return {
            "status": "skipped",
            "reason": "semgrep_not_installed",
            "findings": [],
            "total": 0,
        }

    # Strict isolation: our config directory only, no auto config, telemetry off (RULES B3)
    argv = [
        "semgrep",
        "scan",
        f"--config={SEMGREP_RULES_DIR}",
        "--json",
        "--metrics=off",
        "--disable-version-check",
        "--quiet",
        str(source_dir),
    ]

    try:
        proc = run_tool(argv, timeout=120.0, cwd=str(SEMGREP_RULES_DIR.parent))
        raw_output = proc.stdout.decode("utf-8", errors="replace").strip()
        data = json.loads(raw_output) if raw_output else {}
    except Exception:
        data = {}

    results_raw = data.get("results", [])
    findings: List[Dict[str, Any]] = []

    for item in results_raw:
        full_path = item.get("path", "")
        try:
            rel = str(Path(full_path).relative_to(source_dir))
        except Exception:
            rel = Path(full_path).name

        extra = item.get("extra", {})
        findings.append({
            "file": rel,
            "line": item.get("start", {}).get("line", 1),
            "col": item.get("start", {}).get("col", 1),
            "check_id": item.get("check_id", ""),
            "severity": extra.get("severity", "WARNING").upper(),
            "message": extra.get("message", ""),
        })

    return {
        "status": "completed",
        "findings": findings,
        "total": len(findings),
    }
