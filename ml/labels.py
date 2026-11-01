"""Ground-truth label extractors for file and repo ML models (RULES D11 & ARCHITECTURE 9.5).

Thresholds are frozen before training.
"""

import math
from typing import Any, Dict, List, Set

# FROZEN THRESHOLDS (RULES D11)
FROZEN_THRESHOLDS = {
    "past_months_window": 12,
    "future_months_window": 6,
    "healthy_min_monthly_commits": 4.0,
    "healthy_past_ratio": 0.5,
    "healthy_min_authors": 2,
    "declining_past_ratio": 0.5,
}

HEALTH_CLASSES = ["Inactive", "Declining", "Moderately Active", "Healthy"]


def compute_file_bug_labels(
    future_commits: List[Dict[str, Any]],
    files: List[str],
) -> Dict[str, int]:
    """Determine bug_risk binary label for each file based on future bugfix commits.

    Label is 1 if any bug-fix commit touches the file in the 6-month future window, else 0.
    """
    touched_by_bugfix: Set[str] = set()

    for commit in future_commits:
        if commit.get("is_bugfix"):
            for f in commit.get("files", []):
                touched_by_bugfix.add(f.get("path"))

    labels: Dict[str, int] = {}
    for fpath in files:
        labels[fpath] = 1 if fpath in touched_by_bugfix else 0

    return labels


def compute_file_maintenance_labels(
    future_commits: List[Dict[str, Any]],
    files: List[str],
) -> Dict[str, float]:
    """Determine continuous maintenance effort label: log1p(added + deleted lines in future 6m)."""
    churn_by_file: Dict[str, int] = {f: 0 for f in files}

    for commit in future_commits:
        for f in commit.get("files", []):
            path = f.get("path")
            if path in churn_by_file:
                churn_by_file[path] += f.get("added", 0) + f.get("deleted", 0)

    return {
        path: round(math.log1p(churn), 4)
        for path, churn in churn_by_file.items()
    }


def compute_repo_health_label(
    past_commits: List[Dict[str, Any]],
    future_commits: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute 4-class repo health label based on activity in past 12m vs future 6m.

    Classes: Inactive, Declining, Moderately Active, Healthy.
    """
    past_months = FROZEN_THRESHOLDS["past_months_window"]
    future_months = FROZEN_THRESHOLDS["future_months_window"]

    r_past = len(past_commits) / float(past_months)
    r_fut = len(future_commits) / float(future_months)

    future_authors = {c.get("author") for c in future_commits if c.get("author")}
    distinct_future_authors = len(future_authors)

    if r_fut == 0:
        label = "Inactive"
        class_id = 0
    elif 0 < r_fut < (FROZEN_THRESHOLDS["declining_past_ratio"] * r_past):
        label = "Declining"
        class_id = 1
    elif (
        r_fut >= (FROZEN_THRESHOLDS["healthy_past_ratio"] * r_past)
        and r_fut >= FROZEN_THRESHOLDS["healthy_min_monthly_commits"]
        and distinct_future_authors >= FROZEN_THRESHOLDS["healthy_min_authors"]
    ):
        label = "Healthy"
        class_id = 3
    else:
        label = "Moderately Active"
        class_id = 2

    return {
        "label": label,
        "class_id": class_id,
        "r_past": round(r_past, 2),
        "r_fut": round(r_fut, 2),
        "distinct_future_authors": distinct_future_authors,
        "past_commits_count": len(past_commits),
        "future_commits_count": len(future_commits),
    }
