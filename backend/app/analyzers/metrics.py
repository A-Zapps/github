"""Code metrics analyzer using Lizard (multi-language) and Radon (Python)."""

import math
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional

import lizard
from radon.complexity import cc_visit
from radon.metrics import h_visit, mi_visit


def _calc_p90(values: List[float]) -> float:
    """Calculate 90th percentile of a list of numeric values."""
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * 0.90
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    d0 = sorted_vals[int(f)] * (c - k)
    d1 = sorted_vals[int(c)] * (k - f)
    return float(round(d0 + d1, 2))


def analyze_file_metrics(file_path: Path, rel_path: str, content: Optional[str] = None) -> Dict[str, Any]:
    """Analyze single file metrics using Lizard and Radon."""
    if content is None:
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            content = ""

    lines = content.splitlines()
    loc = len(lines)

    # 1. Lizard analysis
    # lizard.analyze_file.analyze_source_code takes filename and code
    file_info = lizard.analyze_file.analyze_source_code(str(rel_path), content)
    nloc = getattr(file_info, "nloc", 0)
    token_count = getattr(file_info, "token_count", 0)

    functions: List[Dict[str, Any]] = []
    ccns: List[int] = []
    params: List[int] = []

    for func in getattr(file_info, "function_list", []):
        ccn = getattr(func, "cyclomatic_complexity", 1)
        param_count = len(getattr(func, "parameters", []))
        ccns.append(ccn)
        params.append(param_count)
        functions.append({
            "name": getattr(func, "name", ""),
            "long_name": getattr(func, "long_name", ""),
            "start_line": getattr(func, "start_line", 1),
            "end_line": getattr(func, "end_line", 1),
            "nloc": getattr(func, "nloc", 0),
            "ccn": ccn,
            "token_count": getattr(func, "token_count", 0),
            "param_count": param_count,
        })

    n_functions = len(functions)
    ccn_max = max(ccns) if ccns else 0
    ccn_mean = round(statistics.mean(ccns), 2) if ccns else 0.0
    ccn_p90 = _calc_p90(ccns) if ccns else 0.0
    params_max = max(params) if params else 0

    is_python = rel_path.lower().endswith(".py")
    radon_cc: Optional[List[Dict[str, Any]]] = None
    radon_mi: Optional[float] = None
    halstead_metrics: Optional[Dict[str, Any]] = None
    mi_proxy = False

    if is_python and content.strip():
        try:
            cc_blocks = cc_visit(content)
            radon_cc = [
                {
                    "name": block.name,
                    "type": getattr(block, "letter", "F"),
                    "lineno": block.lineno,
                    "col_offset": getattr(block, "col_offset", 0),
                    "complexity": block.complexity,
                    "rank": getattr(block, "rank", "A"),
                }
                for block in cc_blocks
            ]
        except Exception:
            radon_cc = []

        try:
            radon_mi = round(float(mi_visit(content, multi=False)), 2)
        except Exception:
            radon_mi = None

        try:
            h_res = h_visit(content)
            if hasattr(h_res, "total"):
                tot = h_res.total
                halstead_metrics = {
                    "h1": tot.h1,
                    "h2": tot.h2,
                    "N1": tot.N1,
                    "N2": tot.N2,
                    "vocabulary": tot.vocabulary,
                    "length": tot.length,
                    "calculated_length": round(tot.calculated_length, 2),
                    "volume": round(tot.volume, 2),
                    "difficulty": round(tot.difficulty, 2),
                    "effort": round(tot.effort, 2),
                    "time": round(tot.time, 2),
                    "bugs": round(tot.bugs, 4),
                }
        except Exception:
            halstead_metrics = None
    else:
        # Lizard-based maintainability index proxy for non-Python
        # Standard SEI maintainability index proxy: 171 - 5.2 * ln(Halstead/NLOC) - 0.23 * CCN
        # We proxy it cleanly bounded to [0.0, 100.0]
        mi_proxy = True
        if nloc > 0:
            raw_mi = 171.0 - 5.2 * math.log(max(1, nloc)) - 0.23 * (ccn_mean or 1.0)
            # Scale raw SEI (which is nominally 0 to 171) to 0-100 scale: (raw_mi * 100 / 171)
            radon_mi = round(max(0.0, min(100.0, raw_mi * 100.0 / 171.0)), 2)
        else:
            radon_mi = 100.0

    return {
        "rel_path": rel_path,
        "loc": loc,
        "nloc": nloc,
        "n_functions": n_functions,
        "ccn_max": ccn_max,
        "ccn_mean": ccn_mean,
        "ccn_p90": ccn_p90,
        "token_count": token_count,
        "params_max": params_max,
        "functions": functions,
        "radon_cc": radon_cc,
        "maintainability_index": radon_mi,
        "maintainability_index_is_proxy": mi_proxy,
        "halstead": halstead_metrics,
    }


def analyze_repository_metrics(source_dir: Path, source_files: List[str]) -> Dict[str, Any]:
    """Analyze all source files in the materialized directory."""
    files_metrics: Dict[str, Dict[str, Any]] = {}
    total_loc = 0
    total_nloc = 0
    total_functions = 0
    all_ccns: List[int] = []
    mi_scores: List[float] = []
    files_over_1000 = 0
    functions_gt_10 = 0

    for rel_path in source_files:
        full_path = source_dir / rel_path
        if not full_path.is_file():
            continue

        metrics = analyze_file_metrics(full_path, rel_path)
        files_metrics[rel_path] = metrics

        total_loc += metrics["loc"]
        total_nloc += metrics["nloc"]
        total_functions += metrics["n_functions"]

        if metrics["loc"] > 1000:
            files_over_1000 += 1

        for fn in metrics["functions"]:
            ccn = fn["ccn"]
            all_ccns.append(ccn)
            if ccn > 10:
                functions_gt_10 += 1

        if metrics["maintainability_index"] is not None:
            mi_scores.append(metrics["maintainability_index"])

    total_files = len(files_metrics)
    ccn_mean = round(statistics.mean(all_ccns), 2) if all_ccns else 0.0
    ccn_max = max(all_ccns) if all_ccns else 0
    ccn_p90 = _calc_p90(all_ccns) if all_ccns else 0.0

    fn_gt_10_ratio = round((functions_gt_10 / total_functions) * 100, 2) if total_functions > 0 else 0.0
    files_over_1000_ratio = round((files_over_1000 / total_files) * 100, 2) if total_files > 0 else 0.0
    avg_mi = round(statistics.mean(mi_scores), 2) if mi_scores else 100.0

    return {
        "total_files": total_files,
        "total_loc": total_loc,
        "total_nloc": total_nloc,
        "total_functions": total_functions,
        "ccn_mean": ccn_mean,
        "ccn_max": ccn_max,
        "ccn_p90": ccn_p90,
        "functions_ccn_gt_10_count": functions_gt_10,
        "functions_ccn_gt_10_ratio": fn_gt_10_ratio,
        "files_over_1000_loc_count": files_over_1000,
        "files_over_1000_loc_ratio": files_over_1000_ratio,
        "avg_maintainability_index": avg_mi,
        "files": files_metrics,
    }
