"""Quality scoring and technical debt calculation service."""

from pathlib import Path
from typing import Any, Dict

import yaml

SCORING_FILE = Path(__file__).resolve().parent.parent / "analyzers" / "scoring.yaml"


def load_scoring_config() -> Dict[str, Any]:
    """Load scoring weights and tech debt parameters from YAML."""
    if SCORING_FILE.is_file():
        try:
            return yaml.safe_load(SCORING_FILE.read_text(encoding="utf-8")) or {}
        except Exception:
            pass
    return {
        "weights": {
            "complexity": 0.20,
            "maintainability": 0.20,
            "duplication": 0.15,
            "lint_density": 0.15,
            "test_ratio": 0.15,
            "file_size_outliers": 0.15,
        },
        "tech_debt_minutes": {
            "complexity_function_gt_10": 45,
            "maintainability_index_below_50": 60,
            "duplicated_block": 30,
            "lint_error": 30,
            "lint_warning": 15,
            "lint_refactor": 20,
            "lint_convention": 10,
            "file_over_1000_loc": 90,
        },
    }


def calculate_quality_scores(
    inventory: Dict[str, Any],
    metrics: Dict[str, Any],
    duplication: Dict[str, Any],
    lint: Dict[str, Any],
) -> Dict[str, Any]:
    """Calculate component scores, weighted overall score, and tech debt."""
    config = load_scoring_config()
    weights = config.get("weights", {}).copy()
    td_config = config.get("tech_debt_minutes", {})

    # 1. Complexity score: 100 - (ratio of functions with CCN > 10 * 100)
    fn_gt_10_ratio = metrics.get("functions_ccn_gt_10_ratio", 0.0)
    complexity_score = round(max(0.0, min(100.0, 100.0 - fn_gt_10_ratio * 2.5)), 1)

    # 2. Maintainability score: average MI
    maintainability_score = round(metrics.get("avg_maintainability_index", 100.0), 1)

    # 3. Duplication score: 100 - (duplication percentage * 2.5)
    dup_pct = duplication.get("duplication_percentage", 0.0)
    duplication_score = round(max(0.0, min(100.0, 100.0 - dup_pct * 3.0)), 1)

    # 4. Lint density: issues per 1,000 LOC
    has_python = any(f.endswith(".py") for f in inventory.get("files", []))
    total_loc = max(1, metrics.get("total_loc", 1))
    pylint_data = lint.get("pylint", {})
    lint_total = pylint_data.get("total", 0)

    if has_python and lint_total >= 0:
        issues_per_kloc = (lint_total / total_loc) * 1000.0
        lint_score = round(max(0.0, min(100.0, 100.0 - issues_per_kloc * 2.0)), 1)
    else:
        # Redistribute lint weight if not applicable
        lint_score = None
        removed_weight = weights.pop("lint_density", 0.15)
        sum_remaining = sum(weights.values()) or 1.0
        for k in weights:
            weights[k] = round(weights[k] + (weights[k] / sum_remaining) * removed_weight, 4)

    # 5. Test ratio: test files / source files
    test_files_count = inventory.get("test_files_count", 0)
    source_files_count = max(1, inventory.get("source_files_count", 1))
    test_ratio = test_files_count / source_files_count
    # 20%+ test ratio gets 100
    test_score = round(max(0.0, min(100.0, (test_ratio / 0.20) * 100.0)), 1)

    # 6. File size outliers: share of files > 1,000 lines
    file_outliers_ratio = metrics.get("files_over_1000_loc_ratio", 0.0)
    outliers_score = round(max(0.0, min(100.0, 100.0 - file_outliers_ratio * 5.0)), 1)

    component_scores = {
        "complexity": {
            "score": complexity_score,
            "weight": weights.get("complexity", 0.20),
            "metric_value": f"{fn_gt_10_ratio}% functions CCN > 10",
        },
        "maintainability": {
            "score": maintainability_score,
            "weight": weights.get("maintainability", 0.20),
            "metric_value": f"{maintainability_score} avg MI",
        },
        "duplication": {
            "score": duplication_score,
            "weight": weights.get("duplication", 0.15),
            "metric_value": f"{dup_pct}% duplicated lines",
        },
        "test_ratio": {
            "score": test_score,
            "weight": weights.get("test_ratio", 0.15),
            "metric_value": f"{round(test_ratio * 100, 1)}% test-to-source ratio",
        },
        "file_size_outliers": {
            "score": outliers_score,
            "weight": weights.get("file_size_outliers", 0.15),
            "metric_value": f"{file_outliers_ratio}% files > 1,000 LOC",
        },
    }

    if lint_score is not None:
        component_scores["lint_density"] = {
            "score": lint_score,
            "weight": weights.get("lint_density", 0.15),
            "metric_value": f"{round(lint_total / total_loc * 1000, 1)} issues/kLOC",
        }

    # Calculate overall weighted score
    weighted_sum = sum(comp["score"] * comp["weight"] for comp in component_scores.values())
    overall_score = round(weighted_sum, 1)

    if overall_score >= 90:
        grade = "A"
    elif overall_score >= 80:
        grade = "B"
    elif overall_score >= 70:
        grade = "C"
    elif overall_score >= 60:
        grade = "D"
    else:
        grade = "F"

    # Tech debt calculation in minutes
    total_minutes = 0
    total_minutes += metrics.get("functions_ccn_gt_10_count", 0) * td_config.get("complexity_function_gt_10", 45)
    total_minutes += duplication.get("duplicate_blocks_count", 0) * td_config.get("duplicated_block", 30)
    total_minutes += metrics.get("files_over_1000_loc_count", 0) * td_config.get("file_over_1000_loc", 90)

    # Lint tech debt breakdown
    by_type = pylint_data.get("by_type", {})
    total_minutes += by_type.get("error", 0) * td_config.get("lint_error", 30)
    total_minutes += by_type.get("warning", 0) * td_config.get("lint_warning", 15)
    total_minutes += by_type.get("refactor", 0) * td_config.get("lint_refactor", 20)
    total_minutes += by_type.get("convention", 0) * td_config.get("lint_convention", 10)

    debt_hours = round(total_minutes / 60.0, 1)
    debt_days = round(debt_hours / 8.0, 1)

    # Worst 10 files by complexity & maintainability
    file_records = []
    for rel_path, f_metrics in metrics.get("files", {}).items():
        file_records.append({
            "path": rel_path,
            "loc": f_metrics.get("loc", 0),
            "ccn_max": f_metrics.get("ccn_max", 0),
            "ccn_mean": f_metrics.get("ccn_mean", 0.0),
            "maintainability_index": f_metrics.get("maintainability_index", 100.0),
            "is_proxy": f_metrics.get("maintainability_index_is_proxy", False),
        })

    # Sort files by highest CCN and lowest MI
    file_records.sort(key=lambda x: (-x["ccn_max"], x["maintainability_index"]))
    worst_files = file_records[:10]

    return {
        "overall_score": overall_score,
        "grade": grade,
        "components": component_scores,
        "weights": weights,
        "tech_debt": {
            "minutes": total_minutes,
            "hours": debt_hours,
            "days": debt_days,
            "label": "estimate from fixed rules, not measured",
        },
        "worst_files": worst_files,
    }
