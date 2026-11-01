"""Tests for developer statistics, bus factor, heatmap, and PR/issue closure velocity (T5.3)."""

from backend.app.analyzers.developer_stats import compute_developer_statistics


def test_hand_checked_developer_statistics():
    # 10 synthetic commits across 3 authors:
    # Alice: 6 commits (60%)
    # Bob: 3 commits (30%)
    # Charlie: 1 commit (10%)
    commits = [
        {"author": "Alice", "iso_date": "2026-05-04T10:00:00Z", "files": [{"added": 50, "deleted": 10}]},  # Mon 10:00
        {"author": "Alice", "iso_date": "2026-05-04T11:00:00Z", "files": [{"added": 20, "deleted": 5}]},   # Mon 11:00
        {"author": "Alice", "iso_date": "2026-05-05T14:00:00Z", "files": [{"added": 30, "deleted": 0}]},   # Tue 14:00
        {"author": "Alice", "iso_date": "2026-05-06T09:00:00Z", "files": [{"added": 15, "deleted": 2}]},   # Wed 09:00
        {"author": "Alice", "iso_date": "2026-05-07T16:00:00Z", "files": [{"added": 40, "deleted": 8}]},   # Thu 16:00
        {"author": "Alice", "iso_date": "2026-05-08T12:00:00Z", "files": [{"added": 10, "deleted": 0}]},   # Fri 12:00
        {"author": "Bob", "iso_date": "2026-05-04T15:00:00Z", "files": [{"added": 80, "deleted": 20}]},    # Mon 15:00
        {"author": "Bob", "iso_date": "2026-05-05T16:00:00Z", "files": [{"added": 40, "deleted": 10}]},    # Tue 16:00
        {"author": "Bob", "iso_date": "2026-05-06T17:00:00Z", "files": [{"added": 60, "deleted": 15}]},    # Wed 17:00
        {"author": "Charlie", "iso_date": "2026-05-07T11:00:00Z", "files": [{"added": 5, "deleted": 1}]},  # Thu 11:00
    ]

    res = compute_developer_statistics(commits)

    assert res["total_commits"] == 10
    assert res["distinct_contributors"] == 3

    # Check Alice
    alice = res["contributors"][0]
    assert alice["author"] == "Alice"
    assert alice["commits"] == 6
    assert alice["percentage"] == 60.0
    assert alice["lines_added"] == 165
    assert alice["lines_deleted"] == 25

    # Check Bob
    bob = res["contributors"][1]
    assert bob["author"] == "Bob"
    assert bob["commits"] == 3
    assert bob["percentage"] == 30.0
    assert bob["lines_added"] == 180
    assert bob["lines_deleted"] == 45

    # Check Charlie
    charlie = res["contributors"][2]
    assert charlie["author"] == "Charlie"
    assert charlie["commits"] == 1
    assert charlie["percentage"] == 10.0

    # Bus factor: Alice alone accounts for 60% (>= 50%), so bus factor is 1
    assert res["bus_factor"] == 1
    assert "High Risk" in res["bus_factor_label"]

    # Heatmap sum MUST equal 10
    heatmap = res["commit_rhythm_heatmap"]
    assert len(heatmap) == 7
    for row in heatmap:
        assert len(row) == 24
    assert sum(sum(r) for r in heatmap) == 10


def test_unavailable_stats_marked_false():
    # Only 1 commit and no PRs or issues
    commits = [{"author": "Dev", "iso_date": "2026-01-01T12:00:00Z"}]
    res = compute_developer_statistics(commits, pull_requests=[], issues=[])

    assert res["pr_merge_time"]["available"] is False
    assert res["issue_close_time"]["available"] is False
    assert "Insufficient" in res["pr_merge_time"]["reason"]
    assert "Insufficient" in res["issue_close_time"]["reason"]


def test_pr_and_issue_closure_calculation():
    commits = [{"author": "Dev", "iso_date": "2026-01-01T12:00:00Z"}]

    prs = [
        {"created_at": "2026-01-01T00:00:00Z", "merged_at": "2026-01-01T10:00:00Z"},  # 10 hrs
        {"created_at": "2026-01-02T00:00:00Z", "merged_at": "2026-01-02T20:00:00Z"},  # 20 hrs
        {"created_at": "2026-01-03T00:00:00Z", "merged_at": "2026-01-04T06:00:00Z"},  # 30 hrs
    ]

    issues = [
        {"created_at": "2026-01-01T00:00:00Z", "closed_at": "2026-01-01T05:00:00Z"},  # 5 hrs
        {"created_at": "2026-01-02T00:00:00Z", "closed_at": "2026-01-02T15:00:00Z"},  # 15 hrs
        {"created_at": "2026-01-03T00:00:00Z", "closed_at": "2026-01-04T01:00:00Z"},  # 25 hrs
    ]

    res = compute_developer_statistics(commits, pull_requests=prs, issues=issues)

    assert res["pr_merge_time"]["available"] is True
    assert res["pr_merge_time"]["median_hours"] == 20.0
    assert res["pr_merge_time"]["count"] == 3

    assert res["issue_close_time"]["available"] is True
    assert res["issue_close_time"]["median_hours"] == 15.0
    assert res["issue_close_time"]["count"] == 3
