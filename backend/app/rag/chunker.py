"""Function-aware and sliding-window code chunker for repository RAG (T7.1, ARCHITECTURE 11)."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

MAX_FILE_BYTES_FOR_RAG = 200 * 1024  # Skip files over 200 KB
WINDOW_SIZE = 60
WINDOW_OVERLAP = 10


def chunk_file_content(
    file_path: str,
    content: str,
    functions: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Chunk a single file's text content using function boundaries when available, or sliding windows."""
    lines = content.splitlines(keepends=True)
    total_lines = len(lines)
    if total_lines == 0:
        return []

    chunks: List[Dict[str, Any]] = []

    # If Lizard functions are provided and valid, use function ranges
    if functions:
        sorted_funcs = sorted(
            [f for f in functions if f.get("start_line") and f.get("end_line")],
            key=lambda x: x["start_line"],
        )
        last_covered = 0

        for fn in sorted_funcs:
            s_line = max(1, int(fn["start_line"]))
            e_line = min(total_lines, int(fn["end_line"]))
            if e_line < s_line:
                continue

            # If there's a substantial gap before this function, chunk the gap
            if s_line - last_covered > 15:
                gap_start = last_covered + 1
                gap_end = s_line - 1
                gap_text = "".join(lines[gap_start - 1 : gap_end])
                if gap_text.strip():
                    chunks.append({
                        "path": file_path,
                        "start_line": gap_start,
                        "end_line": gap_end,
                        "text": gap_text,
                        "function_name": None,
                    })

            func_text = "".join(lines[s_line - 1 : e_line])
            if func_text.strip():
                chunks.append({
                    "path": file_path,
                    "start_line": s_line,
                    "end_line": e_line,
                    "text": func_text,
                    "function_name": fn.get("name"),
                })
            last_covered = max(last_covered, e_line)

        # Trailing lines after last function
        if total_lines - last_covered > 15:
            trail_text = "".join(lines[last_covered:])
            if trail_text.strip():
                chunks.append({
                    "path": file_path,
                    "start_line": last_covered + 1,
                    "end_line": total_lines,
                    "text": trail_text,
                    "function_name": None,
                })

        if chunks:
            return chunks

    # Fallback: 60-line windows with 10 lines overlap
    step = WINDOW_SIZE - WINDOW_OVERLAP
    for i in range(0, total_lines, step):
        chunk_lines = lines[i : i + WINDOW_SIZE]
        s_line = i + 1
        e_line = i + len(chunk_lines)
        chunk_text = "".join(chunk_lines)
        if chunk_text.strip():
            chunks.append({
                "path": file_path,
                "start_line": s_line,
                "end_line": e_line,
                "text": chunk_text,
                "function_name": None,
            })

    return chunks


def chunk_repository(
    src_dir: Path,
    source_files: List[str],
    lizard_files: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Chunk all eligible source files in repository directory. Skip files over 200 KB."""
    func_map_by_path: Dict[str, List[Dict[str, Any]]] = {}
    if lizard_files:
        items = lizard_files.values() if isinstance(lizard_files, dict) else lizard_files
        for lf in items:
            if isinstance(lf, dict):
                fname = lf.get("rel_path") or lf.get("filename") or ""
                func_map_by_path[fname] = lf.get("functions", [])

    all_chunks: List[Dict[str, Any]] = []

    for rel_path in source_files:
        full_path = src_dir / rel_path
        if not full_path.is_file():
            continue

        try:
            sz = os.path.getsize(full_path)
            if sz > MAX_FILE_BYTES_FOR_RAG:
                continue

            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            file_funcs = func_map_by_path.get(rel_path)
            file_chunks = chunk_file_content(rel_path, content, file_funcs)
            all_chunks.extend(file_chunks)
        except Exception:
            continue

    return all_chunks
