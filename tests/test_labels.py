"""Tests for ML ground-truth labels and frozen thresholds (RULES D11)."""

import math

from ml.labels import (
    FROZEN_THRESHOLDS,
    compute_file_bug_labels,
    compute_file_maintenance_labels,
    compute_repo_health_label,
)


def test_frozen_thresholds_intact():
    """Verify frozen thresholds match ARCHITECTURE 9.5 and cannot be altered."""
    assert FROZEN_THRESHOLDS["past_months_window"] == 12
    assert FROZEN_THRESHOLDS["future_months_window"] == 6
    assert FROZEN_THRESHOLDS["healthy_min_monthly_commits"] == 4.0
    assert FROZEN_THRESHOLDS["healthy_past_ratio"] == 0.5
    assert FROZEN_THRESHOLDS["healthy_min_authors"] == 2
    assert FROZEN_THRESHOLDS["declining_past_ratio"] == 0.5


def test_file_bug_and_maintenance_labels():
    """Verify bugfix label (0 or 1) and continuous maintenance churn label (log1p)."""
    future_commits = [
        {
            "is_bugfix": False,
            "files": [{"path": "feature.py", "added": 100, "deleted": 10}],
        },
        {
            "is_bugfix": True,
            "files": [{"path": "buggy.py", "added": 5, "deleted": 2}],
        },
    ]

    files = ["feature.py", "buggy.py", "untouched.py"]

    bug_labels = compute_file_bug_labels(future_commits, files)
    assert bug_labels["buggy.py"] == 1
    assert bug_labels["feature.py"] == 0
    assert bug_labels["untouched.py"] == 0

    maint_labels = compute_file_maintenance_labels(future_commits, files)
    assert maint_labels["feature.py"] == round(math.log1p(110), 4)
    assert maint_labels["buggy.py"] == round(math.log1p(7), 4)
    assert maint_labels["untouched.py"] == 0.0


def test_repo_health_all_four_classes():
    """Verify repo health classification into all 4 distinct classes."""
    # 1. Inactive: r_fut == 0
    past = [{"author": "dev"}] * 24  # r_past = 24/12 = 2.0
    fut_inactive = []
    res_inactive = compute_repo_health_label(past, fut_inactive)
    assert res_inactive["label"] == "Inactive"
    assert res_inactive["class_id"] == 0

    # 2. Declining: 0 < r_fut < 0.5 * r_past
    # r_past = 120/12 = 10.0; 0.5 * r_past = 5.0
    # r_fut with 12 commits in 6m = 12/6 = 2.0 (< 5.0)
    past_active = [{"author": "dev"}] * 120
    fut_declining = [{"author": "dev"}] * 12
    res_declining = compute_repo_health_label(past_active, fut_declining)
    assert res_declining["label"] == "Declining"
    assert res_declining["class_id"] == 1

    # 3. Healthy: r_fut >= 0.5 * r_past AND r_fut >= 4 AND >= 2 authors
    # r_past = 60/12 = 5.0
    # r_fut with 36 commits in 6m = 36/6 = 6.0 (>= 2.5 and >= 4.0), authors: Alice, Bob
    past_mod = [{"author": "alice"}] * 60
    fut_healthy = (
        [{"author": "alice"}] * 18
        + [{"author": "bob"}] * 18
    )
    res_healthy = compute_repo_health_label(past_mod, fut_healthy)
    assert res_healthy["label"] == "Healthy"
    assert res_healthy["class_id"] == 3

    # 4. Moderately Active: does not meet Healthy criteria (e.g. only 1 author)
    fut_one_author = [{"author": "alice"}] * 36
    res_moderate = compute_repo_health_label(past_mod, fut_one_author)
    assert res_moderate["label"] == "Moderately Active"
    assert res_moderate["class_id"] == 2
