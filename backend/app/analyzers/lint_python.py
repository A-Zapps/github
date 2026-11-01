"""Python static linting service executing Pylint and Bandit with strict default configs."""

import json
from pathlib import Path
from typing import Any, Dict, List

from backend.app.core.subprocess_runner import run_tool

CURRENT_DIR = Path(__file__).resolve().parent
DEFAULT_PYLINTRC = CURRENT_DIR / "pylint_default.rc"
DEFAULT_BANDIT_CONF = CURRENT_DIR / "bandit_default.yaml"
MAX_SAMPLED_FILES = 50


def run_pylint_analysis(source_dir: Path, python_files: List[str]) -> Dict[str, Any]:
    """Execute Pylint using our default rcfile and return structured findings."""
    if not python_files:
        return {"messages": [], "by_type": {}, "total": 0}

    # Sample top files by length/importance
    sampled = python_files[:MAX_SAMPLED_FILES]
    # Build absolute paths for targets
    target_paths = [str(source_dir / f) for f in sampled if (source_dir / f).is_file()]
    if not target_paths:
        return {"messages": [], "by_type": {}, "total": 0}

    # Strict isolation: always pass our explicit rcfile (RULES B3)
    argv = [
        "pylint",
        f"--rcfile={DEFAULT_PYLINTRC}",
        "--output-format=json",
        "--reports=no",
        "--score=no",
    ] + target_paths

    try:
        proc = run_tool(argv, timeout=90.0, cwd=str(CURRENT_DIR))
        raw_output = proc.stdout.decode("utf-8", errors="replace").strip()
        messages_raw = json.loads(raw_output) if raw_output else []
    except Exception:
        messages_raw = []

    messages: List[Dict[str, Any]] = []
    by_type: Dict[str, int] = {}

    for item in messages_raw:
        m_type = item.get("type", "warning")
        by_type[m_type] = by_type.get(m_type, 0) + 1

        # Make path relative to source_dir for privacy and clean display
        full_path = item.get("path", "")
        try:
            rel = str(Path(full_path).relative_to(source_dir))
        except Exception:
            rel = Path(full_path).name

        messages.append({
            "file": rel,
            "line": item.get("line", 1),
            "column": item.get("column", 1),
            "symbol": item.get("symbol", ""),
            "message_id": item.get("message-id", ""),
            "type": m_type,
            "message": item.get("message", ""),
        })

    return {
        "messages": messages,
        "by_type": by_type,
        "total": len(messages),
        "sampled_files_count": len(target_paths),
    }


def run_bandit_analysis(source_dir: Path, python_files: List[str]) -> Dict[str, Any]:
    """Execute Bandit using our default config and return security findings."""
    if not python_files:
        return {"findings": [], "by_severity": {}, "total": 0}

    sampled = python_files[:MAX_SAMPLED_FILES]
    target_paths = [str(source_dir / f) for f in sampled if (source_dir / f).is_file()]
    if not target_paths:
        return {"findings": [], "by_severity": {}, "total": 0}

    # Strict isolation: always pass our config and avoid reading repo ini files (RULES B3)
    argv = [
        "bandit",
        "-c",
        str(DEFAULT_BANDIT_CONF),
        "-f",
        "json",
        "-q",
    ] + target_paths

    try:
        proc = run_tool(argv, timeout=90.0, cwd=str(CURRENT_DIR))
        raw_output = proc.stdout.decode("utf-8", errors="replace").strip()
        data = json.loads(raw_output) if raw_output else {}
    except Exception:
        data = {}

    results_raw = data.get("results", [])
    findings: List[Dict[str, Any]] = []
    by_severity: Dict[str, int] = {}

    for item in results_raw:
        sev = item.get("issue_severity", "LOW").upper()
        by_severity[sev] = by_severity.get(sev, 0) + 1

        full_path = item.get("filename", "")
        try:
            rel = str(Path(full_path).relative_to(source_dir))
        except Exception:
            rel = Path(full_path).name

        findings.append({
            "file": rel,
            "line": item.get("line_number", 1),
            "test_id": item.get("test_id", ""),
            "severity": sev,
            "confidence": item.get("issue_confidence", "LOW").upper(),
            "text": item.get("issue_text", ""),
        })

    return {
        "findings": findings,
        "by_severity": by_severity,
        "total": len(findings),
        "sampled_files_count": len(target_paths),
    }


def analyze_python_lint(source_dir: Path, python_files: List[str]) -> Dict[str, Any]:
    """Execute unified Python linting and security checking."""
    pylint_res = run_pylint_analysis(source_dir, python_files)
    bandit_res = run_bandit_analysis(source_dir, python_files)

    return {
        "pylint": pylint_res,
        "bandit": bandit_res,
        "total_issues": pylint_res["total"] + bandit_res["total"],
    }
