"""Code duplication detector using 6-line normalized sliding window hashing."""

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

WINDOW_SIZE = 6


def _normalize_line(line: str) -> str:
    """Normalize line by trimming leading/trailing whitespace."""
    return " ".join(line.strip().split())


def detect_duplication(
    source_dir: Path,
    source_files: List[str],
    window_size: int = WINDOW_SIZE,
) -> Dict[str, Any]:
    """Detect duplicate code blocks across source files using normalized window hashing.

    Returns total duplication percentage, duplicated lines count, and block details.
    """
    # Map hash -> list of (file_rel_path, start_line, end_line)
    window_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    file_lines_map: Dict[str, int] = {}
    file_raw_lines: Dict[str, List[Tuple[int, str]]] = {}  # 1-based original line number and normalized line

    for rel_path in source_files:
        full_path = source_dir / rel_path
        if not full_path.is_file():
            continue

        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        raw_lines = content.splitlines()
        file_lines_map[rel_path] = len(raw_lines)

        # Collect non-empty normalized lines along with their original 1-based line number
        normalized_with_num: List[Tuple[int, str]] = []
        for idx, line in enumerate(raw_lines, start=1):
            norm = _normalize_line(line)
            if norm and not norm.startswith(("#", "//", "/*", "*")):
                normalized_with_num.append((idx, norm))

        file_raw_lines[rel_path] = normalized_with_num

        # Slide window
        n = len(normalized_with_num)
        if n >= window_size:
            for i in range(n - window_size + 1):
                window = normalized_with_num[i : i + window_size]
                text_block = "\n".join(item[1] for item in window)
                block_hash = hashlib.sha256(text_block.encode("utf-8")).hexdigest()
                start_line = window[0][0]
                end_line = window[-1][0]
                window_map[block_hash].append({
                    "file": rel_path,
                    "start_line": start_line,
                    "end_line": end_line,
                    "window_idx": i,
                })

    # Identify duplicate hashes: hashes that appear in >= 2 distinct locations
    # Filter overlapping windows in the same file to prevent self-counting adjacent 1-line slides
    duplicate_blocks: List[Dict[str, Any]] = []
    file_duplicated_line_numbers: Dict[str, Set[int]] = defaultdict(set)

    for block_hash, occurrences in window_map.items():
        # Clean occurrences so that two occurrences in the same file aren't overlapping windows
        distinct_occurrences: List[Dict[str, Any]] = []
        last_by_file: Dict[str, int] = {}
        for occ in occurrences:
            fname = occ["file"]
            w_idx = occ["window_idx"]
            if fname not in last_by_file or (w_idx - last_by_file[fname]) >= window_size:
                distinct_occurrences.append(occ)
                last_by_file[fname] = w_idx

        if len(distinct_occurrences) >= 2:
            duplicate_blocks.append({
                "hash": block_hash,
                "lines": window_size,
                "occurrences_count": len(distinct_occurrences),
                "instances": [
                    {
                        "file": occ["file"],
                        "start_line": occ["start_line"],
                        "end_line": occ["end_line"],
                    }
                    for occ in distinct_occurrences
                ],
            })

            # Record line numbers as duplicated
            for occ in distinct_occurrences:
                fname = occ["file"]
                s = occ["start_line"]
                e = occ["end_line"]
                for lno in range(s, e + 1):
                    file_duplicated_line_numbers[fname].add(lno)

    total_lines = sum(file_lines_map.values())
    total_duplicate_lines = sum(len(lines) for lines in file_duplicated_line_numbers.values())
    duplication_percentage = (
        round((total_duplicate_lines / total_lines) * 100, 2) if total_lines > 0 else 0.0
    )

    per_file_duplication: Dict[str, Dict[str, Any]] = {}
    for rel_path, l_count in file_lines_map.items():
        dup_count = len(file_duplicated_line_numbers.get(rel_path, set()))
        pct = round((dup_count / l_count) * 100, 2) if l_count > 0 else 0.0
        per_file_duplication[rel_path] = {
            "total_lines": l_count,
            "duplicate_lines": dup_count,
            "duplication_percentage": pct,
        }

    return {
        "total_lines": total_lines,
        "duplicate_lines": total_duplicate_lines,
        "duplication_percentage": duplication_percentage,
        "duplicate_blocks_count": len(duplicate_blocks),
        "duplicate_blocks": duplicate_blocks[:50],  # Top 50 duplicate blocks
        "files": per_file_duplication,
    }
