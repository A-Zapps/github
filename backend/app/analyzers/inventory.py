"""File inventory, language identification, and test detection (F2)."""

import os
import re
from typing import Any, Dict, List

EXTENSION_LANGUAGE_MAP: Dict[str, str] = {
    ".py": "Python",
    ".pyw": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".hpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "CSS",
    ".sass": "CSS",
    ".less": "CSS",
    ".sh": "Shell",
    ".bash": "Shell",
    ".ps1": "PowerShell",
    ".bat": "Batch",
    ".cmd": "Batch",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".sql": "SQL",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".txt": "Text",
}

TEST_DIR_PATTERNS = {
    "test", "tests", "__tests__", "spec", "specs", "testing"
}

TEST_FILE_REGEX = re.compile(
    r"(^test_|_test\.py$|\.test\.[jt]sx?$|\.spec\.[jt]sx?$|Test\.java$|_test\.go$|_spec\.rb$)",
    re.IGNORECASE,
)


def detect_language(filepath: str) -> str:
    """Identify programming or markup language from file extension."""
    _, ext = os.path.splitext(filepath)
    return EXTENSION_LANGUAGE_MAP.get(ext.lower(), "Other")


def is_test_file(relpath: str) -> bool:
    """Determine whether a file is a unit/integration test."""
    normalized = relpath.replace("\\", "/").lower()
    parts = normalized.split("/")

    # Check directory names (e.g. test, tests, test_utils, testing)
    if any(
        p in TEST_DIR_PATTERNS or p.startswith("test") or p.endswith("test") or "_test" in p
        for p in parts[:-1]
    ):
        return True

    # Check filename pattern
    filename = parts[-1]
    return bool(TEST_FILE_REGEX.search(filename))


def scan_inventory(root_dir: str) -> Dict[str, Any]:
    """Inspect and inventory all files under root_dir."""
    files_list: List[Dict[str, Any]] = []
    lang_stats: Dict[str, Dict[str, int]] = {}
    test_files_count = 0
    source_files_count = 0
    total_lines = 0

    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            abs_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(abs_path, root_dir).replace("\\", "/")

            lang = detect_language(filename)
            is_test = is_test_file(rel_path)

            line_count = 0
            try:
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    line_count = sum(1 for _ in f)
            except Exception:
                pass

            total_lines += line_count
            if is_test:
                test_files_count += 1
            else:
                source_files_count += 1

            if lang not in lang_stats:
                lang_stats[lang] = {"files": 0, "lines": 0}
            lang_stats[lang]["files"] += 1
            lang_stats[lang]["lines"] += line_count

            files_list.append({
                "path": rel_path,
                "language": lang,
                "lines": line_count,
                "is_test": is_test,
            })

    total_files = len(files_list)
    test_ratio = round(test_files_count / max(source_files_count, 1), 3)

    return {
        "total_files": total_files,
        "total_lines": total_lines,
        "languages": lang_stats,
        "test_files_count": test_files_count,
        "source_files_count": source_files_count,
        "test_to_source_ratio": test_ratio,
        "files": files_list,
    }
